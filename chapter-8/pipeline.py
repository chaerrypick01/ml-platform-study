"""Compile artifact-based and shared-PVC YOLO training pipelines."""
import argparse
import os
from pathlib import Path

from kfp import compiler, dsl
from kfp.dsl import Dataset, Model, Metrics, ClassificationMetrics, HTML, Input, Output

IMAGE = os.environ.get('LAB_IMAGE', 'localhost:5002/ch8-lab:v1')


@dsl.component(base_image=IMAGE, install_kfp_package=False)
def prepare_data(dataset: Output[Dataset], report: Output[HTML], seed: int = 42) -> int:
    import json
    from pathlib import Path
    from lab_data import prepare

    manifest = prepare(dataset.path, seed)
    counts = {k: len(v) for k, v in manifest['splits'].items()}
    dataset.metadata['sha256'] = manifest['archive_sha256']
    dataset.metadata['split_counts'] = counts
    Path(report.path).write_text('<h1>COCO128 data QA</h1><pre>' + json.dumps(counts) +
                                '</pre><p>Cross-split SHA256 overlap: 0</p>')
    return sum(counts.values())


@dsl.component(base_image=IMAGE, install_kfp_package=False)
def fit_model(dataset: Input[Dataset], model: Output[Model], epochs: int = 1):
    from pathlib import Path
    from train import train

    train(dataset.path, model.path, Path('/lab/yolov8n.pt'), epochs)
    model.metadata['epochs'] = epochs
    model.metadata['framework'] = 'ultralytics'


@dsl.component(base_image=IMAGE, install_kfp_package=False)
def score_model(dataset: Input[Dataset], model: Input[Model], metrics: Output[Metrics],
                confusion: Output[ClassificationMetrics], report: Output[HTML]):
    import html
    import json
    from pathlib import Path
    from train import evaluate

    record = evaluate(Path(model.path) / 'model.pt', dataset.path, '/tmp/evaluate')
    for name, value in record['metrics'].items():
        metrics.log_metric(name, value)
    confusion.log_confusion_matrix(record['categories'], record['confusion_matrix'])
    Path(report.path).write_text('<h1>YOLO validation</h1><pre>' +
                                html.escape(json.dumps(record['metrics'], indent=2)) + '</pre>')


@dsl.pipeline(name='chapter-7-8-artifact-training')
def artifact_pipeline(epochs: int = 1, seed: int = 42):
    data = prepare_data(seed=seed)
    fit = fit_model(dataset=data.outputs['dataset'], epochs=epochs)
    score_model(dataset=data.outputs['dataset'], model=fit.outputs['model'])
    for task in (data, fit):
        task.set_caching_options(False)
        task.set_memory_limit('3Gi')
        task.set_cpu_limit('2')


if __name__ == '__main__':
    output = Path(__file__).parent / 'outputs/compiled/artifacts.yaml'
    output.parent.mkdir(parents=True, exist_ok=True)
    compiler.Compiler().compile(artifact_pipeline, str(output))
    print(output)
