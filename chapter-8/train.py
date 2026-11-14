"""YOLO checkpoint evaluation and same-host CPU/MPS timing experiments."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

os.environ.setdefault('MPLBACKEND', 'Agg')
os.environ.setdefault('YOLO_AUTOINSTALL', 'false')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'chapter-7'))
from lab_data import configure


def evaluate(weights, dataset, output, device='cpu', split='val'):
    from ultralytics import YOLO

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(weights))
    result = model.val(data=str(configure(dataset)), split=split, imgsz=320,
                       batch=8, device=device, workers=0, plots=True,
                       project=str(output), name='validation', exist_ok=True)
    metrics = {k: float(v) for k, v in result.results_dict.items()}
    matrix = result.confusion_matrix.matrix
    record = {'weights': str(weights), 'weights_sha256': hashlib.sha256(Path(weights).read_bytes()).hexdigest(),
              'split': split, 'device': device, 'metrics': metrics,
              'confusion_matrix': matrix.astype(int).T.tolist(),
              'categories': list(model.names.values()) + ['background']}
    (output / 'evaluation.json').write_text(json.dumps(record, indent=2))
    return record


def train(dataset, output, weights, epochs, device='cpu', tracking_uri=None):
    import torch
    from torch.utils.tensorboard import SummaryWriter
    from ultralytics import YOLO, settings

    settings.update({'mlflow': False, 'tensorboard': False})
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    writer = SummaryWriter(str(output / 'tensorboard'))
    model = YOLO(str(weights))
    durations = []
    started = [0.0]
    run = None
    if tracking_uri:
        import mlflow
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment('chapter-8-9-yolo')
        run = mlflow.start_run(run_name=f'yolov8n-{device}-{epochs}epochs')
        mlflow.log_params({'epochs': epochs, 'device': device, 'imgsz': 320,
                           'batch': 8, 'seed': 42, 'initial_weights': Path(weights).name})
        mlflow.log_artifact(str(Path(dataset) / 'manifest.json'))

    def begin(trainer):
        if device == 'mps':
            torch.mps.synchronize()
        started[0] = time.perf_counter()

    def end(trainer):
        if device == 'mps':
            torch.mps.synchronize()
        elapsed = time.perf_counter() - started[0]
        durations.append(elapsed)
        scalars = {k: float(v) for k, v in trainer.label_loss_items(trainer.tloss, prefix='train').items()}
        scalars['time/train_epoch_seconds'] = elapsed
        for key, value in scalars.items():
            writer.add_scalar(key, value, trainer.epoch)
        if run:
            mlflow.log_metrics(scalars, step=trainer.epoch)
        writer.flush()

    model.add_callback('on_train_epoch_start', begin)
    model.add_callback('on_train_epoch_end', end)
    wall_start = time.perf_counter()
    success = False
    try:
        model.train(data=str(configure(dataset)), epochs=epochs, imgsz=320,
                    batch=8, device=device, workers=0, seed=42, deterministic=True,
                    project=str(output), name='fit', exist_ok=False, pretrained=True,
                    amp=False, plots=False, save=True, save_period=1,
                    optimizer='SGD', lr0=0.001, patience=0, close_mosaic=0)
        wall = time.perf_counter() - wall_start
        shutil.copy2(output / 'fit/weights/last.pt', output / 'model.pt')
        result = evaluate(output / 'model.pt', dataset, output / 'eval', device)
        record = {'epochs': epochs, 'device': device, 'wall_seconds': wall,
                  'train_epoch_seconds': durations, 'torch_version': torch.__version__,
                  'evaluation': result, 'mlflow_run_id': run.info.run_id if run else None}
        (output / 'result.json').write_text(json.dumps(record, indent=2))
        if run:
            mlflow.log_metrics({k.replace('(', '_').replace(')', ''): v
                                for k, v in result['metrics'].items()})
            mlflow.log_metric('wall_seconds', wall)
            mlflow.log_artifact(str(output / 'model.pt'))
            mlflow.log_artifact(str(output / 'fit/results.csv'))
        success = True
        return record
    finally:
        writer.close()
        if run:
            mlflow.end_run(status='FINISHED' if success else 'FAILED')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['train', 'evaluate'])
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--weights', type=Path, required=True)
    parser.add_argument('--epochs', type=int, default=10)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--split', default='val', choices=['val', 'test'])
    parser.add_argument('--tracking-uri')
    args = parser.parse_args()
    if args.action == 'train':
        train(args.dataset, args.output, args.weights, args.epochs, args.device, args.tracking_uri)
    else:
        evaluate(args.weights, args.dataset, args.output, args.device, args.split)
