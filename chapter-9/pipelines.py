"""Compile artifact-based and shared-PVC YOLO training pipelines."""
import argparse
import os
from pathlib import Path

from kfp import compiler, dsl, kubernetes
from kfp.dsl import Dataset, Model, Metrics, ClassificationMetrics, HTML, Input, Output

IMAGE = os.environ.get('LAB_IMAGE', 'localhost:5002/ch9-lab:v1')


@dsl.component(base_image=IMAGE, install_kfp_package=False)
def stage_pvc(run_folder: str, seed: int = 42) -> str:
    from pathlib import Path
    from lab_data import prepare

    if not run_folder.replace('-', '').replace('_', '').isalnum():
        raise ValueError('run_folder must be a simple unique directory name')
    root = Path('/shared') / run_folder
    prepare(root / 'dataset', seed)
    return str(root)


@dsl.component(base_image=IMAGE, install_kfp_package=False)
def train_pvc(root: str, epochs: int, tracking_uri: str) -> str:
    from pathlib import Path
    from train import train

    train(Path(root) / 'dataset', Path(root) / 'training', Path('/lab/yolov8n.pt'),
          epochs, 'cpu', tracking_uri or None)
    return str(Path(root) / 'training')


@dsl.component(base_image=IMAGE, install_kfp_package=False)
def inspect_pvc(root: str, training_folder: str, metrics: Output[Metrics], report: Output[HTML]):
    import html
    import json
    from pathlib import Path
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    record = json.loads((Path(training_folder) / 'result.json').read_text())
    events = EventAccumulator(str(Path(training_folder) / 'tensorboard')).Reload()
    tags = events.Tags()['scalars']
    if 'train/box_loss' not in tags:
        raise ValueError(f'Expected loss scalar, got {tags}')
    for name, value in record['evaluation']['metrics'].items():
        metrics.log_metric(name, value)
    report.metadata['tensorboard_tags'] = tags
    report.metadata['mlflow_run_id'] = record['mlflow_run_id']
    Path(report.path).write_text('<h1>PVC training</h1><pre>' + html.escape(json.dumps(
        {'root': root, 'tensorboard_tags': tags, 'mlflow_run_id': record['mlflow_run_id']}, indent=2)) + '</pre>')


@dsl.pipeline(name='chapter-9-pvc-training')
def pvc_pipeline(run_folder: str, pvc_name: str = 'chapter9-data', epochs: int = 1,
                 tracking_uri: str = 'http://host.docker.internal:5001'):
    stage = stage_pvc(run_folder=run_folder)
    fit = train_pvc(root=stage.output, epochs=epochs, tracking_uri=tracking_uri)
    inspect = inspect_pvc(root=stage.output, training_folder=fit.output)
    for task in (stage, fit, inspect):
        kubernetes.mount_pvc(task, pvc_name=pvc_name, mount_path='/shared')
        task.set_caching_options(False)
        task.set_memory_limit('3Gi')
        task.set_cpu_limit('2')


@dsl.component(base_image=IMAGE, install_kfp_package=False)
def train_recommender(metrics: Output[Metrics], report: Output[HTML],
                      tracking_uri: str = 'http://host.docker.internal:5001'):
    import html
    import json
    from pathlib import Path
    from recommend import run

    result = run('/tmp/movie', tracking_uri)
    for name in ('best_val_rmse', 'test_rmse', 'test_mean_baseline_rmse'):
        metrics.log_metric(name, result[name])
    report.metadata['mlflow_run_id'] = result['mlflow_run_id']
    Path(report.path).write_text('<h1>MovieLens explicit ratings</h1><pre>' +
        html.escape(json.dumps({k: v for k, v in result.items() if k != 'history'}, indent=2)) + '</pre>')


@dsl.pipeline(name='chapter-9-movie-training')
def movie_pipeline():
    task = train_recommender()
    task.set_caching_options(False)
    task.set_memory_limit('2Gi')
    task.set_cpu_limit('2')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'outputs/compiled')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, function in [('pvc', pvc_pipeline), ('movie', movie_pipeline)]:
        compiler.Compiler().compile(function, str(args.output / f'{name}.yaml'))
        print(args.output / f'{name}.yaml')
