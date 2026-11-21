import hashlib
import json
from zipfile import ZipFile

import pandas as pd
import torch


class Recommender:
    def __init__(self, artifacts):
        archive = artifacts / "movielens.zip"
        metadata = json.loads((artifacts / "result.json").read_text())
        if hashlib.sha256(archive.read_bytes()).hexdigest() != metadata["archive_sha256"]:
            raise ValueError("MovieLens archive differs from training input")

        self.model = torch.load(artifacts / "model.pt", map_location="cpu", weights_only=False)
        with ZipFile(archive) as data:
            ratings = pd.read_csv(data.open("ml-latest-small/ratings.csv"))
            self.titles = pd.read_csv(data.open("ml-latest-small/movies.csv")).set_index("movieId").title
        training = ratings.sample(n=metadata["sample_size"], random_state=42).iloc[:metadata["train_rows"]]
        self.seen = training.groupby("userId").movieId.agg(set)

    def recommend(self, user_id):
        model = self.model
        weights = model["state_dict"]
        u = model["users"][user_id]
        scores = (model["mean"] + (weights["user.weight"][u] * weights["movie.weight"]).sum(1)
                  + weights["ub.weight"][u] + weights["mb.weight"][:, 0])
        candidates = [m for m in model["movies"] if m not in self.seen[user_id]]
        ranked = sorted(candidates, key=lambda m: (-scores[model["movies"][m]].item(), m))
        items = [{"movie_id": int(m), "title": self.titles[m],
                  "predicted_rating": round(scores[model["movies"][m]].item(), 3)} for m in ranked[:3]]
        return {"user_id": user_id, "recommendations": items}
