"""Chapter 5's four batch stages, using the existing chapter 4 local services."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from feast import FeatureStore
from minio import Minio

HERE = Path(__file__).resolve().parent
CH4 = HERE.parent / "chapter-4"
SOURCES = {
    "demographic": ("demographic_features.parquet", ["Native_country", "Sex", "Race"]),
    "relationship": ("relationship_features.parquet", ["Relationship", "Marital-Status"]),
    "occupation": ("occupational_features.parquet", ["Workclass", "Education", "Occupation"]),
}
FEATURES = [f"{view}:{col}" for view, (_, cols) in SOURCES.items() for col in cols]
COLUMNS = ["Workclass", "Education", "Marital-Status", "Occupation", "Relationship", "Race", "Sex", "Native_country"]
BUCKET = "chapter5-batch"


def configure():
    # Credentials of the loopback-only chapter 4 tutorial deployment.
    os.environ.update({
        "AWS_ACCESS_KEY_ID": "ch4local", "AWS_SECRET_ACCESS_KEY": "ch4-local-only-password",
        "AWS_DEFAULT_REGION": "us-east-1", "AWS_ENDPOINT_URL": "http://127.0.0.1:19000",
        "FEAST_S3_ENDPOINT_URL": "http://127.0.0.1:19000", "AWS_EC2_METADATA_DISABLED": "true",
    })
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001"))


def s3():
    return Minio("127.0.0.1:19000", access_key="ch4local", secret_key="ch4-local-only-password", secure=False)


def normalize(frame):
    """Match chapter 4's training input; never encode the saved pipeline twice."""
    missing = set(COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing feature columns: {sorted(missing)}")
    result = frame[COLUMNS].copy()
    if result.isna().any().any():
        raise ValueError("Missing Feast values: check user IDs, event timestamps, and TTL.")
    for col in COLUMNS:
        result[col] = result[col].str.strip()
    return result


def read_object(client, key):
    response = client.get_object(BUCKET, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def prepare(work, rows, model_uri):
    if rows <= 0:
        raise ValueError("rows must be positive")
    if (work / "manifest.json").exists():
        raise ValueError("Use a new work directory for each batch.")
    work.mkdir(parents=True, exist_ok=True)
    source = None
    user_order = None
    timestamps = []
    for filename, cols in SOURCES.values():
        frame = pd.read_parquet(CH4 / "feast/feature_data" / filename)
        if frame.user_id.isna().any() or frame.user_id.duplicated().any():
            raise ValueError("Tutorial fixture requires one source row per user.")
        if user_order is None:
            user_order = frame.user_id.tolist()
        elif set(frame.user_id) != set(user_order):
            raise ValueError("Source tables must contain the same user IDs.")
        timestamps.extend(pd.to_datetime(frame.feature_timestamp, utc=True).tolist())
        source = frame[["user_id", *cols]] if source is None else source.merge(
            frame[["user_id", *cols]], on="user_id", validate="one_to_one", how="outer", sort=False
        )
    source = source.set_index("user_id").loc[user_order].reset_index()
    csv_path = CH4 / "data/income_data.csv"
    training = pd.read_csv(csv_path)
    # CSV has no IDs. Verify every row before using its position as a lab-only mapping.
    pd.testing.assert_frame_equal(normalize(source), normalize(training))
    sample = source.head(rows).copy()
    entities = sample[["user_id"]].copy()
    # Today would exceed the feature views' 365-day TTL for this 2023 dataset.
    entities["event_timestamp"] = max(timestamps) + timedelta(seconds=1)
    entities.to_parquet(work / "request.parquet", index=False)
    sample.to_parquet(work / "reference.parquet", index=False)
    if not model_uri:
        model_uri = json.loads((CH4 / "experiments/results/result.json").read_text())["model_uri"]
    manifest = {
        "batch_id": work.name, "rows": len(entities), "model_uri": model_uri,
        "tracking_uri": mlflow.get_tracking_uri(),
        "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "all_source_rows_match_csv": True,
        "event_timestamp": entities.event_timestamp.iloc[0].isoformat(),
        "input_key": f"{work.name}/input.parquet", "output_key": f"{work.name}/predictions.parquet",
    }
    client = s3()
    if not client.bucket_exists(BUCKET):
        client.make_bucket(BUCKET)
    client.fput_object(BUCKET, manifest["input_key"], str(work / "request.parquet"))
    (work / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def read(work, manifest):
    payload = read_object(s3(), manifest["input_key"])
    frame = pd.read_parquet(io.BytesIO(payload))
    if frame.empty or frame.user_id.isna().any() or frame.user_id.duplicated().any():
        raise ValueError("Expected nonempty, unique user IDs.")
    if pd.to_datetime(frame.event_timestamp, utc=True).isna().any():
        raise ValueError("Missing event timestamp")
    (work / "entities.parquet").write_bytes(payload)
    return frame


def retrieve(work, manifest):
    config = work / "feature_repo"
    config.mkdir(exist_ok=True)
    s3().fget_object("feature-registry", "feature_store.yaml", str(config / "feature_store.yaml"))
    entities = pd.read_parquet(work / "entities.parquet")
    features = FeatureStore(repo_path=str(config)).get_historical_features(
        entity_df=entities, features=FEATURES
    ).to_df()
    # Restore request ordering explicitly; do not rely on Feast's output order.
    features = entities.merge(features, on=["user_id", "event_timestamp"], how="left", validate="one_to_one")
    normalize(features)  # Fail before inference if the point-in-time query returned nulls.
    features.to_parquet(work / "features.parquet", index=False)
    return features


def predict(work, manifest):
    mlflow.set_tracking_uri(manifest["tracking_uri"])
    model = mlflow.sklearn.load_model(manifest["model_uri"])
    frame = pd.read_parquet(work / "features.parquet")
    inputs = normalize(frame)
    if list(model.feature_names_in_) != COLUMNS or set(model.classes_) != {0, 1}:
        raise ValueError("Expected chapter 4's eight-feature binary classification pipeline.")
    result = frame[["user_id", "event_timestamp"]].copy()
    result["probability_gt_50k"] = model.predict_proba(inputs)[:, list(model.classes_).index(1)]
    result["predicted_label"] = np.where(model.predict(inputs) == 1, ">50K", "<=50K")
    result["model_uri"] = manifest["model_uri"]
    result.to_parquet(work / "predictions.parquet", index=False)
    return result


def write(work, manifest):
    path = work / "predictions.parquet"
    client = s3()
    client.fput_object(BUCKET, manifest["output_key"], str(path))
    payload = read_object(client, manifest["output_key"])
    if hashlib.sha256(payload).digest() != hashlib.sha256(path.read_bytes()).digest():
        raise AssertionError("MinIO output round-trip mismatch")
    return f"s3://{BUCKET}/{manifest['output_key']}"


def verify(work, manifest):
    mlflow.set_tracking_uri(manifest["tracking_uri"])
    reference = pd.read_parquet(work / "reference.parquet")
    features = pd.read_parquet(work / "features.parquet")
    payload = read_object(s3(), manifest["output_key"])
    if payload != (work / "predictions.parquet").read_bytes():
        raise AssertionError("Stored output differs from local predictions")
    actual = pd.read_parquet(io.BytesIO(payload))
    pd.testing.assert_series_equal(actual.user_id, reference.user_id)
    pd.testing.assert_frame_equal(normalize(features), normalize(reference))
    model = mlflow.sklearn.load_model(manifest["model_uri"])
    expected_probability = model.predict_proba(normalize(reference))[:, list(model.classes_).index(1)]
    # Parallel forest reductions can differ at floating-point round-off precision.
    np.testing.assert_allclose(actual.probability_gt_50k, expected_probability, rtol=0, atol=1e-12)
    np.testing.assert_array_equal(actual.predicted_label, np.where(model.predict(normalize(reference)) == 1, ">50K", "<=50K"))
    report = {**manifest, "source_features_match": True, "direct_predictions_match": True,
              "probability_absolute_tolerance": 1e-12,
              "probability_max_absolute_difference": float(np.max(np.abs(actual.probability_gt_50k - expected_probability))),
              "output_round_trip_match": True, "output_uri": f"s3://{BUCKET}/{manifest['output_key']}",
              "label_counts": actual.predicted_label.value_counts().to_dict()}
    (work / "verification.json").write_text(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=["prepare", "read", "retrieve", "predict", "write", "verify", "all"])
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--rows", type=int, default=100)
    parser.add_argument("--model-uri", help="Default: model pinned in chapter 4 results/result.json")
    args = parser.parse_args()
    configure()
    if args.step not in {"prepare", "all"} and args.work_dir is None:
        parser.error("--work-dir is required for an existing batch")
    work = args.work_dir or HERE / "outputs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    if args.step in {"prepare", "all"}:
        manifest = prepare(work, args.rows, args.model_uri)
    else:
        manifest = json.loads((work / "manifest.json").read_text())
    stages = {"read": read, "retrieve": retrieve, "predict": predict, "write": write, "verify": verify}
    for name in (stages if args.step == "all" else [args.step]):
        if name in stages:
            result = stages[name](work, manifest)
            print(f"{name}: {len(result) if isinstance(result, pd.DataFrame) else result}", flush=True)
    print(f"Work directory: {work}")


if __name__ == "__main__":
    main()
