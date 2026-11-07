"""Submit compiled KFP IR to an explicitly selected KFP endpoint."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import kfp

HERE = Path(__file__).resolve().parent
FEATURES = ('demographic:Native_country,demographic:Sex,demographic:Race,'
            'relationship:Relationship,relationship:Marital-Status,'
            'occupation:Workclass,occupation:Education,occupation:Occupation')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--kfp-endpoint', required=True, help='KFP API URL reached by this client')
    parser.add_argument('--minio-endpoint', required=True, help='S3 endpoint reachable inside the task Pods')
    parser.add_argument('--mlflow-endpoint', required=True, help='Tracking endpoint reachable inside the task Pods')
    parser.add_argument('--manifest', type=Path, required=True, help='Input manifest produced by batch_inference.py prepare')
    parser.add_argument('--pipeline', type=Path, default=HERE / 'income_classifier_pipeline.yaml')
    parser.add_argument('--output-key', required=True, help='New output object key for this KFP run')
    parser.add_argument('--wait', action='store_true')
    parser.add_argument('--record', type=Path, help='Save run ID and parameters as JSON')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    client = kfp.Client(host=args.kfp_endpoint)
    pipeline_name = 'chapter5-income-classifier'
    pipeline_id = client.get_pipeline_id(pipeline_name)
    if pipeline_id is None:
        pipeline_id = client.upload_pipeline(str(args.pipeline), pipeline_name=pipeline_name).pipeline_id
    version = client.upload_pipeline_version(
        str(args.pipeline), pipeline_id=pipeline_id,
        pipeline_version_name=datetime.now(timezone.utc).strftime('lab-%Y%m%dT%H%M%S%fZ'))
    experiment = client.create_experiment('chapter-5')
    parameters = {'minio_endpoint': args.minio_endpoint, 'mlflow_endpoint': args.mlflow_endpoint,
                   'input_bucket': 'chapter5-batch', 'input_key': manifest['input_key'],
                   'feature_config_bucket': 'feature-registry',
                   'feature_config_key': 'chapter5/feature_store.yaml', 'features': FEATURES,
                   'model_uri': manifest['model_uri'], 'output_bucket': 'chapter5-batch',
                   'output_key': args.output_key}
    run = client.run_pipeline(
        experiment_id=experiment.experiment_id, job_name=f"income-{manifest['batch_id']}",
        pipeline_id=pipeline_id, version_id=version.pipeline_version_id, params=parameters,
        enable_caching=False,
    )
    print('Run ID:', run.run_id, flush=True)
    record = {'run_id': run.run_id, 'kfp_endpoint': args.kfp_endpoint,
              'pipeline_id': pipeline_id, 'pipeline_version_id': version.pipeline_version_id,
              'experiment_id': experiment.experiment_id, 'parameters': parameters,
              'manifest': str(args.manifest.resolve()), 'output_key': args.output_key,
              'model_uri': manifest['model_uri']}
    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(json.dumps(record, indent=2))
    if args.wait:
        result = client.wait_for_run_completion(run.run_id, timeout=1800, sleep_duration=10)
        print('State:', result.state)
        record['state'] = result.state
        if args.record:
            args.record.write_text(json.dumps(record, indent=2))
        if result.state != 'SUCCEEDED':
            raise SystemExit(f'Pipeline did not succeed: {result.state}')
