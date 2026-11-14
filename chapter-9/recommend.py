"""A small explicit-rating MovieLens exercise with MLflow and TensorBoard."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

import mlflow
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.tensorboard import SummaryWriter

URL = 'https://files.grouplens.org/datasets/movielens/ml-latest-small.zip'


def run(output, tracking_uri, epochs=10):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    torch.manual_seed(42)
    archive = output / 'movielens.zip'
    urllib.request.urlretrieve(URL, archive)
    with zipfile.ZipFile(archive) as stream:
        with stream.open('ml-latest-small/ratings.csv') as source:
            ratings = pd.read_csv(source).sample(n=6400, random_state=42).reset_index(drop=True)
    train = ratings.iloc[:5120].copy()
    users = {v: i for i, v in enumerate(sorted(train.userId.unique()))}
    movies = {v: i for i, v in enumerate(sorted(train.movieId.unique()))}

    def encode(frame):
        known = frame.userId.isin(users) & frame.movieId.isin(movies)
        frame = frame[known]
        return (torch.tensor(frame.userId.map(users).to_numpy(), dtype=torch.long),
                torch.tensor(frame.movieId.map(movies).to_numpy(), dtype=torch.long),
                torch.tensor(frame.rating.to_numpy(), dtype=torch.float32)), int((~known).sum())

    training, _ = encode(train)
    validation, val_unknown = encode(ratings.iloc[5120:5760])
    testing, test_unknown = encode(ratings.iloc[5760:])
    mean = float(training[2].mean())

    class Factorization(nn.Module):
        def __init__(self):
            super().__init__()
            self.user = nn.Embedding(len(users), 16)
            self.movie = nn.Embedding(len(movies), 16)
            self.ub = nn.Embedding(len(users), 1)
            self.mb = nn.Embedding(len(movies), 1)
            nn.init.normal_(self.user.weight, std=0.05)
            nn.init.normal_(self.movie.weight, std=0.05)
            nn.init.zeros_(self.ub.weight)
            nn.init.zeros_(self.mb.weight)

        def forward(self, u, m):
            return mean + (self.user(u) * self.movie(m)).sum(1) + self.ub(u).squeeze(1) + self.mb(m).squeeze(1)

    def rmse(model, data):
        with torch.no_grad():
            return float(((model(data[0], data[1]).clamp(0.5, 5) - data[2]) ** 2).mean().sqrt())

    model = Factorization()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=0.0001)
    writer = SummaryWriter(str(output / 'tensorboard'))
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment('chapter-9-movielens')
    history = []
    best_score = float('inf')
    best = None
    with mlflow.start_run(run_name='explicit-ratings-6400') as active:
        mlflow.log_params({'sample_size': 6400, 'epochs': epochs, 'seed': 42, 'factors': 16,
                           'task': 'explicit-rating-regression', 'selection': 'validation-rmse'})
        try:
            for epoch in range(epochs):
                model.train()
                indices = torch.randperm(len(training[0]))
                for index in indices.split(256):
                    optimizer.zero_grad()
                    predicted = model(training[0][index], training[1][index])
                    loss = ((predicted - training[2][index]) ** 2).mean()
                    loss.backward()
                    optimizer.step()
                model.eval()
                scores = {'train_rmse': rmse(model, training), 'val_rmse': rmse(model, validation)}
                history.append(scores)
                for name, value in scores.items():
                    writer.add_scalar(name, value, epoch)
                mlflow.log_metrics(scores, step=epoch)
                if scores['val_rmse'] < best_score:
                    best_score = scores['val_rmse']
                    best = copy.deepcopy(model.state_dict())
            model.load_state_dict(best)
            baseline = float(((testing[2] - mean) ** 2).mean().sqrt())
            result = {'mlflow_run_id': active.info.run_id, 'source_url': URL,
                      'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                      'sample_size': 6400, 'train_rows': len(training[0]),
                      'val_rows': len(validation[0]), 'test_rows': len(testing[0]),
                      'excluded_unseen_val': val_unknown, 'excluded_unseen_test': test_unknown,
                      'best_val_rmse': best_score, 'test_rmse': rmse(model, testing),
                      'test_mean_baseline_rmse': baseline, 'history': history}
            torch.save({'state_dict': best, 'users': users, 'movies': movies, 'mean': mean}, output / 'model.pt')
            (output / 'result.json').write_text(json.dumps(result, indent=2))
            mlflow.log_metrics({'best_val_rmse': best_score, 'test_rmse': result['test_rmse'],
                                'test_mean_baseline_rmse': baseline})
            mlflow.log_artifact(str(output / 'result.json'))
            mlflow.log_artifact(str(output / 'model.pt'))
            print(json.dumps({k: v for k, v in result.items() if k != 'history'}), flush=True)
            return result
        finally:
            writer.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tracking-uri', default='http://127.0.0.1:5001')
    parser.add_argument('--epochs', type=int, default=10)
    args = parser.parse_args()
    run(args.output, args.tracking_uri, args.epochs)
