"""One process per KFP task; artifact paths are supplied by the KFP launcher."""
import argparse
import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from minio import Minio


def client(endpoint):
    url = urlparse(endpoint)
    if url.scheme not in {'http', 'https'} or not url.netloc:
        raise ValueError('MinIO endpoint must include http:// or https://')
    return Minio(url.netloc, access_key=os.environ['AWS_ACCESS_KEY_ID'],
                 secret_key=os.environ['AWS_SECRET_ACCESS_KEY'], secure=url.scheme == 'https')


def read(args):
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    client(args.minio_endpoint).fget_object(args.bucket, args.key, args.output)
    frame = pd.read_parquet(args.output)
    if frame.empty or frame.user_id.isna().any() or frame.user_id.duplicated().any():
        raise ValueError('Expected nonempty unique user IDs')
    if pd.to_datetime(frame.event_timestamp, utc=True).isna().any():
        raise ValueError('Missing event timestamp')
    print(f'Read {len(frame)} entities')


def retrieve(args):
    from feast import FeatureStore
    os.environ.update(AWS_ENDPOINT_URL=args.minio_endpoint,
                      FEAST_S3_ENDPOINT_URL=args.minio_endpoint,
                      AWS_DEFAULT_REGION='us-east-1', AWS_EC2_METADATA_DISABLED='true')
    config = Path('/tmp/chapter5-feature-repo')
    config.mkdir(exist_ok=True)
    client(args.minio_endpoint).fget_object(args.bucket, args.key, str(config / 'feature_store.yaml'))
    entities = pd.read_parquet(args.input)
    store = FeatureStore(repo_path=str(config))
    frame = store.get_historical_features(entity_df=entities, features=args.features.split(',')).to_df()
    frame = entities.merge(frame, on=['user_id', 'event_timestamp'], how='left', validate='one_to_one')
    cols = [feature.split(':', 1)[1] for feature in args.features.split(',')]
    if frame[cols].isna().any().any():
        raise ValueError('Missing point-in-time features; check user IDs and TTL')
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.output, index=False)
    print(f'Retrieved {len(frame)} rows, {len(cols)} features')


def predict(args):
    import mlflow
    import mlflow.sklearn
    import numpy as np
    mlflow.set_tracking_uri(args.mlflow_endpoint)
    model = mlflow.sklearn.load_model(args.model_uri)
    frame = pd.read_parquet(args.input)
    cols = list(model.feature_names_in_)
    inputs = frame[cols].copy()
    if inputs.isna().any().any():
        raise ValueError('Missing model features')
    for col in cols:
        inputs[col] = inputs[col].str.strip()
    if set(model.classes_) != {0, 1}:
        raise ValueError('Expected chapter 4 binary classifier')
    output = frame[['user_id', 'event_timestamp']].copy()
    output['probability_gt_50k'] = model.predict_proba(inputs)[:, list(model.classes_).index(1)]
    output['predicted_label'] = np.where(model.predict(inputs) == 1, '>50K', '<=50K')
    output['model_uri'] = args.model_uri
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(args.output, index=False)
    print(f'Predicted {len(output)} rows using {args.model_uri}')


def write(args):
    storage = client(args.minio_endpoint)
    storage.fput_object(args.bucket, args.key, args.input)
    response = storage.get_object(args.bucket, args.key)
    try:
        actual = hashlib.sha256(response.read()).digest()
    finally:
        response.close()
        response.release_conn()
    if actual != hashlib.sha256(Path(args.input).read_bytes()).digest():
        raise AssertionError('Output upload verification failed')
    print(f'Verified s3://{args.bucket}/{args.key}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    stages = parser.add_subparsers(dest='step', required=True)
    for name in ['read', 'retrieve', 'predict', 'write']:
        stage = stages.add_parser(name)
        if name != 'predict':
            for flag in ['minio-endpoint', 'bucket', 'key']:
                stage.add_argument('--' + flag, required=True)
        if name != 'read':
            stage.add_argument('--input', required=True)
        if name != 'write':
            stage.add_argument('--output', required=True)
        if name == 'retrieve':
            stage.add_argument('--features', required=True)
        if name == 'predict':
            stage.add_argument('--mlflow-endpoint', required=True)
            stage.add_argument('--model-uri', required=True)
    args = parser.parse_args()
    {'read': read, 'retrieve': retrieve, 'predict': predict, 'write': write}[args.step](args)
