"""Check actual KFP task states; preserve API responses as local evidence."""
import argparse
import json
from pathlib import Path

import kfp


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--records', nargs='+', type=Path, default=[
        Path(__file__).parent / f'outputs/{mode}-run.json' for mode in ('artifacts',)])
    args = parser.parse_args()
    client = kfp.Client(host='http://127.0.0.1:8080')
    expected = {'artifacts': {'prepare-data', 'fit-model', 'score-model'}}
    failed = False
    for path in args.records:
        record = json.loads(path.read_text())
        result = client.get_run(record['run_id']).to_dict()
        path.with_suffix('.status.json').write_text(json.dumps(result, indent=2, default=str))
        tasks = result.get('run_details', {}).get('task_details', [])
        succeeded = {t['display_name'] for t in tasks if t['state'] == 'SUCCEEDED'}
        okay = result['state'] == 'SUCCEEDED' and expected[record['mode']].issubset(succeeded)
        print(json.dumps({'mode': record['mode'], 'run_id': record['run_id'],
                          'state': result['state'], 'expected_tasks_succeeded': okay,
                          'succeeded_tasks': sorted(succeeded)}))
        failed |= not okay
    raise SystemExit(1 if failed else 0)
