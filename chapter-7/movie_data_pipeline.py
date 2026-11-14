"""Small MovieLens preparation lab: download, Parquet split, independent QA."""
import argparse
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from kfp import compiler, dsl, Client
from kfp.dsl import Dataset, HTML, Input, Output

IMAGE = os.environ.get('LAB_IMAGE', 'localhost:5002/ch7-data:v1')

@dsl.component(base_image=IMAGE, install_kfp_package=False)
def prepare_movie(dataset: Output[Dataset], seed: int = 42):
    import hashlib
    import json
    import urllib.request
    import zipfile
    from pathlib import Path
    import pandas as pd
    root = Path(dataset.path)
    root.mkdir(parents=True, exist_ok=True)
    archive = root / 'source.zip'
    url = 'https://files.grouplens.org/datasets/movielens/ml-latest-small.zip'
    urllib.request.urlretrieve(url, archive)
    with zipfile.ZipFile(archive) as z:
        with z.open('ml-latest-small/ratings.csv') as f:
            ratings = pd.read_csv(f)
    source_rows = len(ratings)
    ratings = ratings.sample(n=6400, random_state=seed).reset_index(drop=True)
    for split, rows in [('train', ratings.iloc[:5120]), ('val', ratings.iloc[5120:5760]), ('test', ratings.iloc[5760:])]:
        rows.to_parquet(root / f'{split}.parquet', index=False)
    manifest = {'source_url': url, 'source_rows': source_rows, 'seed': seed,
                'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                'sample_rows': 6400, 'split': 'random rows, 80/10/10'}
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    archive.unlink()

@dsl.component(base_image=IMAGE, install_kfp_package=False)
def inspect_movie(dataset: Input[Dataset], report: Output[HTML]):
    import json
    import html
    from pathlib import Path
    import pandas as pd
    root = Path(dataset.path)
    splits = {s: pd.read_parquet(root / f'{s}.parquet') for s in ('train', 'val', 'test')}
    counts = {s: len(f) for s, f in splits.items()}
    assert counts == {'train': 5120, 'val': 640, 'test': 640}, counts
    keys = {}
    for name, frame in splits.items():
        assert list(frame.columns) == ['userId', 'movieId', 'rating', 'timestamp']
        assert not frame.isna().any().any()
        assert frame.rating.between(0.5, 5).all()
        assert (frame[['userId', 'movieId', 'timestamp']] > 0).all().all()
        assert not frame.duplicated(['userId', 'movieId']).any()
        keys[name] = set(zip(frame.userId, frame.movieId))
    assert not (keys['train'] & keys['val'] or keys['train'] & keys['test'] or keys['val'] & keys['test'])
    train = splits['train']
    unseen = {s: int((~f.userId.isin(train.userId) | ~f.movieId.isin(train.movieId)).sum()) for s, f in splits.items() if s != 'train'}
    result = {'counts': counts, 'pair_overlap': 0, 'unseen_user_or_movie_rows': unseen,
              'manifest': json.loads((root / 'manifest.json').read_text()),
              'note': 'QA retains cold-start rows; no model training or temporal evaluation.'}
    report.metadata['qa'] = result
    Path(report.path).write_text('<h1>MovieLens preparation QA</h1><pre>' + html.escape(json.dumps(result, indent=2)) + '</pre>')
    print(json.dumps(result), flush=True)

@dsl.pipeline(name='chapter-7-movielens-data-preparation')
def pipeline():
    prepared = prepare_movie()
    checked = inspect_movie(dataset=prepared.outputs['dataset'])
    for task in (prepared, checked):
        task.set_caching_options(False)
        task.set_memory_limit('1Gi')
        task.set_cpu_limit('1')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--submit', action='store_true')
    args = parser.parse_args()
    out = Path(__file__).parent / 'outputs/movie-data'
    out.mkdir(parents=True, exist_ok=True)
    package = out / 'pipeline.yaml'
    compiler.Compiler().compile(pipeline, str(package))
    if args.submit:
        run = Client(host='http://127.0.0.1:8080').create_run_from_pipeline_package(str(package), arguments={}, experiment_name='chapter-7', run_name='movie-data-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'), enable_caching=False)
        (out / 'run.json').write_text(json.dumps({'run_id': run.run_id}, indent=2))
        print(run.run_id)
