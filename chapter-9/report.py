"""Publish compact, non-data execution evidence and comparison figures."""
import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'chapter-9/results'


if __name__ == '__main__':
    RESULTS.mkdir(parents=True, exist_ok=True)
    summary = json.loads((ROOT / 'chapter-8/outputs/experiment-20261114/summary.json').read_text())
    timing = ROOT / 'chapter-8/outputs/benchmark-20261115/summary.json'
    if timing.exists():
        summary['benchmark'] = json.loads(timing.read_text())
        import statistics
        for record in summary['benchmark'].values():
            record['median_after_first_seconds'] = statistics.median(record['train_epoch_seconds'][1:])
        summary['benchmark_source'] = str(timing.relative_to(ROOT))
        summary['benchmark_note'] = 'Separate 3-epoch CPU/MPS runs; thread count is not asserted by this report.'
    (RESULTS / 'yolo-summary.json').write_text(json.dumps(summary, indent=2))
    data = json.loads((ROOT / 'chapter-7/outputs/coco128/manifest.json').read_text())
    hashes = [{r['image_sha256'] for r in rows} for rows in data['splits'].values()]
    overlap = sum(len(a & b) for i, a in enumerate(hashes) for b in hashes[i + 1:])
    assert overlap == 0, 'Dataset splits overlap'
    (RESULTS / 'data-qa.json').write_text(json.dumps({
        'url': data['url'], 'archive_sha256': data['archive_sha256'], 'seed': data['seed'],
        'counts': {k: len(v) for k, v in data['splits'].items()},
        'cross_split_image_hash_overlap': overlap}, indent=2))
    movie = json.loads((ROOT / 'chapter-9/outputs/movie-local/result.json').read_text())
    (RESULTS / 'movie-summary.json').write_text(json.dumps(movie, indent=2))
    labels = list(summary['comparison'])
    scores = [summary['comparison'][x]['metrics/mAP50-95(B)'] for x in labels]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    bars = axes[0].bar(labels, scores, color=['#64748b', '#0891b2', '#0891b2', '#0891b2'])
    axes[0].bar_label(bars, fmt='%.3f', padding=4)
    axes[0].set(title='Same validation split, CPU evaluation', ylabel='mAP50-95', xlabel='Training checkpoint', ylim=(0, 0.7))
    devices = list(summary['benchmark'])
    values = [summary['benchmark'][d]['median_after_first_seconds'] for d in devices]
    bars = axes[1].bar(devices, values, color=['#64748b', '#0891b2'][:len(devices)])
    axes[1].bar_label(bars, fmt='%.2f s', padding=4)
    axes[1].set(title='Mac host: training epoch after warm-up', ylabel='Seconds (lower is faster)', ylim=(0, max(values) * 1.3))
    fig.savefig(RESULTS / 'yolo-comparison.png', dpi=160)
    plt.close(fig)
    runs = []
    for mode in ('artifacts', 'pvc', 'movie'):
        record = json.loads((ROOT / f'chapter-9/outputs/{mode}-run.json').read_text())
        status = json.loads((ROOT / f'chapter-9/outputs/{mode}-run.status.json').read_text())
        runs.append({'mode': mode, 'run_id': record['run_id'], 'state': status['state'],
                     'parameters': record['parameters'], 'tasks': [
                         {'name': t['display_name'], 'state': t['state']} for t in status['run_details']['task_details']
                         if t['display_name'] in {'prepare-data', 'fit-model', 'score-model', 'stage-pvc',
                                                  'train-pvc', 'inspect-pvc', 'train-recommender'}]})
    (RESULTS / 'kfp-runs.json').write_text(json.dumps(runs, indent=2))
    print(RESULTS)
