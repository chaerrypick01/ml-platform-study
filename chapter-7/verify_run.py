"""Read KFP completion and preserve actual task logs for the follow-up labs."""
import json
from pathlib import Path
import subprocess
import kfp
ROOT = Path(__file__).resolve().parents[1]
KUBE = ['kubectl', '--kubeconfig', str(ROOT/'chapter-5/.kube/config'), '--context', 'kind-ch5-lab', '-n', 'kubeflow']
client = kfp.Client(host='http://127.0.0.1:8080')
failed = False
for directory, expected in [('chapter-7/outputs/movie-data', {'prepare-movie', 'inspect-movie'})]:
    out = ROOT / directory
    record = json.loads((out/'run.json').read_text())
    state = client.get_run(record['run_id']).to_dict()
    (out/'status.json').write_text(json.dumps(state, default=str, indent=2))
    tasks = state.get('run_details', {}).get('task_details', [])
    actual = {t['display_name']: t['state'] for t in tasks if t['display_name'] in expected}
    okay = state['state'] == 'SUCCEEDED' and set(actual) == expected and all(s == 'SUCCEEDED' for s in actual.values())
    failed |= not okay
    print(json.dumps({'run_id':record['run_id'],'state':state['state'],'tasks':actual,'verified':okay}))
    pods = json.loads(subprocess.check_output(KUBE + ['get', 'pods', '-l', 'pipeline/runid=' + record['run_id'], '-o', 'json']))
    for pod in pods['items']:
        name = pod['metadata']['name']
        if 'system-container-impl' in name and pod['status']['phase'] in ('Succeeded', 'Failed'):
            result = subprocess.run(KUBE + ['logs', name, '-c', 'main'], capture_output=True, text=True)
            if result.returncode == 0:
                (out / (name + '.log')).write_text(result.stdout)
raise SystemExit(int(failed))
