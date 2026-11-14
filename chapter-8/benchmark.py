"""Repeat the same three-epoch workload on available Mac backends."""
import argparse
import json
from pathlib import Path
import torch
from train import train

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--weights', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Choose a new output directory')
    torch.set_num_threads(4)
    results = {}
    for device in ['cpu', 'mps'] if torch.backends.mps.is_available() else ['cpu']:
        result = train(args.dataset, args.output / device,
                       args.weights, 3, device)
        results[device] = {k: result[k] for k in ('wall_seconds', 'train_epoch_seconds')}
    (args.output / 'summary.json').write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))
