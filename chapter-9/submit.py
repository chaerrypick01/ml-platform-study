"""Submit only to the local, unauthenticated lab KFP endpoint."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import kfp


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['pvc', 'movie'])
    parser.add_argument('--endpoint', default='http://127.0.0.1:8080')
    parser.add_argument('--epochs', type=int, default=1)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.endpoint != 'http://127.0.0.1:8080':
        raise SystemExit('This script is restricted to the local lab endpoint')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    params = {} if args.mode == 'movie' else {'epochs': args.epochs}
    if args.mode == 'pvc':
        params['run_folder'] = f'ch9-{stamp}'
    client = kfp.Client(host=args.endpoint)
    result = client.create_run_from_pipeline_package(
        str(Path(__file__).parent / f'outputs/compiled/{args.mode}.yaml'),
        arguments=params, experiment_name='chapter-9',
        run_name=f'{args.mode}-{stamp}', enable_caching=False)
    record = {'run_id': result.run_id, 'mode': args.mode, 'parameters': params,
              'endpoint': args.endpoint}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2))
    print(json.dumps(record), flush=True)
