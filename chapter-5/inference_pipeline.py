"""Compile the chapter 5 KFP DAG. Each component runs in its own container."""
import argparse
from pathlib import Path

from kfp import compiler, components, dsl

HERE = Path(__file__).resolve().parent


def build_pipeline(image):
    ops = {}
    for name in ['read_data', 'retrieve_features', 'run_inference', 'write_data']:
        spec = (HERE / 'components' / name / 'component.yaml').read_text()
        ops[name] = components.load_component_from_text(spec.replace('chapter5-inference:lab-v1', image))

    @dsl.pipeline(name='chapter5-income-classifier')
    def pipeline(minio_endpoint: str, mlflow_endpoint: str, input_bucket: str,
                 input_key: str, feature_config_bucket: str, feature_config_key: str,
                 features: str, model_uri: str, output_bucket: str, output_key: str):
        read = ops['read_data'](minio_endpoint=minio_endpoint, bucket=input_bucket, key=input_key)
        retrieve = ops['retrieve_features'](
            minio_endpoint=minio_endpoint, bucket=feature_config_bucket, key=feature_config_key,
            features=features, input_data=read.outputs['data_output'])
        predict = ops['run_inference'](mlflow_endpoint=mlflow_endpoint, model_uri=model_uri,
                                      input_data=retrieve.outputs['data_output'])
        write = ops['write_data'](minio_endpoint=minio_endpoint, bucket=output_bucket,
                                 key=output_key, input_data=predict.outputs['data_output'])
        for task in [read, retrieve, predict, write]:
            task.set_caching_options(False)
            task.set_cpu_request('250m').set_memory_request('512Mi').set_memory_limit('2Gi')
        # Loopback tutorial credentials only; real deployments should inject a Kubernetes Secret.
        for task in [read, retrieve, write]:
            task.set_env_variable('AWS_ACCESS_KEY_ID', 'ch4local')
            task.set_env_variable('AWS_SECRET_ACCESS_KEY', 'ch4-local-only-password')
    return pipeline


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', default='chapter5-inference:lab-v1')
    parser.add_argument('--output', type=Path, default=HERE / 'income_classifier_pipeline.yaml')
    args = parser.parse_args()
    compiler.Compiler().compile(pipeline_func=build_pipeline(args.image), package_path=str(args.output))
    print(args.output)
