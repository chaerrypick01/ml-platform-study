"""Run checkpoint and CPU/MPS comparisons with identical lab parameters."""
import argparse
import json
from pathlib import Path
import platform
import statistics

import torch

from train import evaluate, train


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--weights', type=Path, required=True)
    parser.add_argument('--resume', action='store_true', help='Reuse completed trajectory and timing runs')
    args = parser.parse_args()
    torch.set_num_threads(4)
    args.output.mkdir(parents=True, exist_ok=True)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    baseline = evaluate(args.weights, args.dataset, args.output / 'baseline')
    result_path = args.output / 'trajectory/result.json'
    if args.resume and result_path.exists():
        trajectory = json.loads(result_path.read_text())
    else:
        trajectory = train(args.dataset, args.output / 'trajectory', args.weights, 10, device,
                           'http://127.0.0.1:5001')
    comparisons = {'baseline': baseline}
    checkpoints = {'baseline': args.weights}
    for epoch in (1, 5, 10):
        weights = args.output / f'trajectory/fit/weights/epoch{epoch - 1}.pt'
        checkpoints[str(epoch)] = weights
        comparisons[str(epoch)] = evaluate(weights, args.dataset, args.output / f'eval-{epoch}')
        (args.output / 'checkpoint-comparison.json').write_text(json.dumps(comparisons, indent=2))
    chosen = max(comparisons, key=lambda k: comparisons[k]['metrics']['metrics/mAP50-95(B)'])
    test = evaluate(checkpoints[chosen], args.dataset, args.output / 'heldout-test', split='test')
    benchmark = {}
    for backend in ['cpu'] + (['mps'] if torch.backends.mps.is_available() else []):
        result_path = args.output / f'benchmark-{backend}/result.json'
        if args.resume and result_path.exists():
            result = json.loads(result_path.read_text())
        else:
            result = train(args.dataset, args.output / f'benchmark-{backend}', args.weights, 3, backend)
        times = result['train_epoch_seconds']
        benchmark[backend] = {'wall_seconds': result['wall_seconds'], 'train_epoch_seconds': times,
                              'median_after_first_seconds': statistics.median(times[1:])}
    summary = {'platform': platform.platform(), 'torch_version': torch.__version__,
               'torch_cpu_threads': torch.get_num_threads(), 'mps_available': torch.backends.mps.is_available(),
               'comparison': {k: v['metrics'] for k, v in comparisons.items()},
               'selected_by_validation': chosen, 'selected_test_metrics': test['metrics'],
               'trajectory_mlflow_run_id': trajectory['mlflow_run_id'], 'benchmark': benchmark}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)
