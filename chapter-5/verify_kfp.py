"""Compare a real KFP output with chapter 4's direct model prediction."""
import argparse
import io
import json
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd

import batch_inference as lab


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    record = json.loads(args.record.read_text())
    if record.get('state') != 'SUCCEEDED':
        raise ValueError('KFP must finish successfully before verifying predictions')
    manifest_path = Path(record['manifest'])
    manifest = json.loads(manifest_path.read_text())
    lab.configure()
    reference = pd.read_parquet(manifest_path.parent / 'reference.parquet')
    entities = pd.read_parquet(manifest_path.parent / 'request.parquet')
    actual = pd.read_parquet(io.BytesIO(lab.read_object(lab.s3(), record['output_key'])))
    pd.testing.assert_series_equal(actual.user_id, reference.user_id)
    pd.testing.assert_series_equal(actual.event_timestamp, entities.event_timestamp)
    if not actual.model_uri.eq(manifest['model_uri']).all():
        raise AssertionError('Output model URI mismatch')
    model = mlflow.sklearn.load_model(manifest['model_uri'])
    inputs = lab.normalize(reference)
    expected = model.predict_proba(inputs)[:, list(model.classes_).index(1)]
    np.testing.assert_allclose(actual.probability_gt_50k, expected, rtol=0, atol=1e-12)
    np.testing.assert_array_equal(actual.predicted_label, np.where(model.predict(inputs) == 1, '>50K', '<=50K'))
    report = {
        'runner': 'KFP 2.4.1 on kind', 'kfp_run_id': record['run_id'], 'state': record['state'],
        'rows': len(actual), 'model_uri': manifest['model_uri'],
        'user_ids_and_timestamps_match': True, 'predicted_labels_match': True,
        'probability_max_absolute_difference': float(np.max(np.abs(actual.probability_gt_50k - expected))),
        'probability_absolute_tolerance': 1e-12,
        'label_counts': actual.predicted_label.value_counts().to_dict(),
        'output_uri': f"s3://{lab.BUCKET}/{record['output_key']}",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
