"""Register isolated chapter 5 Feast definitions with Pod-reachable S3 endpoints."""
import argparse
from datetime import timedelta
import os
from pathlib import Path
import tempfile

import yaml
from feast import Entity, FeatureStore, FeatureView, Field, FileSource, ValueType
from feast.types import String

from component import client


def register(endpoint):
    os.environ.update(AWS_ENDPOINT_URL=endpoint, FEAST_S3_ENDPOINT_URL=endpoint,
                      AWS_DEFAULT_REGION='us-east-1', AWS_EC2_METADATA_DISABLED='true')
    config = {
        'project': 'ch5_batch_income',
        'registry': 's3://feature-registry/chapter5/registry.db',
        'provider': 'local', 'entity_key_serialization_version': 2,
        'offline_store': {'type': 'file'},
        'online_store': {'type': 'sqlite', 'path': '/tmp/ch5-online.db'},
    }
    entity = Entity(name='user_id', join_keys=['user_id'], value_type=ValueType.STRING)
    views = []
    for name, filename, cols in [
        ('demographic', 'demographic_features.parquet', ['Native_country', 'Sex', 'Race']),
        ('relationship', 'relationship_features.parquet', ['Relationship', 'Marital-Status']),
        ('occupation', 'occupational_features.parquet', ['Workclass', 'Education', 'Occupation']),
    ]:
        views.append(FeatureView(name=name, entities=[entity], ttl=timedelta(days=365),
                                 schema=[Field(name=col, dtype=String) for col in cols],
                                 source=FileSource(path=f's3://feature-data-sets/{filename}',
                                                   timestamp_field='feature_timestamp',
                                                   s3_endpoint_override=endpoint)))
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'feature_store.yaml'
        path.write_text(yaml.safe_dump(config))
        store = FeatureStore(repo_path=temp)
        store.apply([entity, *views])
        client(endpoint).fput_object('feature-registry', 'chapter5/feature_store.yaml', str(path))
    print('Registered ch5_batch_income; chapter 4 registry unchanged')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--minio-endpoint', required=True)
    register(parser.parse_args().minio_endpoint)
