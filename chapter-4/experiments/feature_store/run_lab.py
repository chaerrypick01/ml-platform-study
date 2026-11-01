"""Run each Feast exercise separately, or all in order. No model training here."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
REPO = HERE / "feature_repo"
DATA = ROOT / "feast" / "feature_data"
OUTPUT = ROOT / "experiments" / "outputs" / "feature-store"

# These credentials belong only to this loopback-bound tutorial deployment.
os.environ.update({
    "AWS_ACCESS_KEY_ID": "ch4local",
    "AWS_SECRET_ACCESS_KEY": "ch4-local-only-password",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_ENDPOINT_URL": "http://127.0.0.1:19000",
    "FEAST_S3_ENDPOINT_URL": "http://127.0.0.1:19000",
    "AWS_EC2_METADATA_DISABLED": "true",
})

import pandas as pd
from feast import FeatureStore
from minio import Minio
from redis import Redis

SOURCES = {
    "demographic": ("demographic_features.parquet", ["Native_country", "Sex", "Race"]),
    "relationship": ("relationship_features.parquet", ["Relationship", "Marital-Status"]),
    "occupation": ("occupational_features.parquet", ["Workclass", "Education", "Occupation"]),
}
FEATURES = [f"{name}:{column}" for name, (_, columns) in SOURCES.items() for column in columns]


def s3():
    return Minio("127.0.0.1:19000", access_key="ch4local", secret_key="ch4-local-only-password", secure=False)


def redis_client():
    return Redis(host="127.0.0.1", port=16379, password="ch4-local-redis", socket_timeout=5)


def save(step, details):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    payload = {"step": step, "checked_at": datetime.now(timezone.utc).isoformat(), **details}
    (OUTPUT / f"{step}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)


def prepare():
    client = s3()
    assert redis_client().ping()
    for bucket in ("feature-data-sets", "feature-registry"):
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
    files = []
    for filename, _ in SOURCES.values():
        source_path = DATA / filename
        # Interpret the tutorial's timezone-less timestamps as UTC; preserve
        # the original file and upload an explicitly timezone-aware copy.
        frame = pd.read_parquet(source_path)
        frame["feature_timestamp"] = pd.to_datetime(frame["feature_timestamp"], utc=True)
        prepared = OUTPUT / "prepared"
        prepared.mkdir(parents=True, exist_ok=True)
        path = prepared / filename
        frame.to_parquet(path, index=False)
        client.fput_object("feature-data-sets", filename, str(path))
        response = client.get_object("feature-data-sets", filename)
        try:
            downloaded_hash = hashlib.sha256(response.read()).hexdigest()
        finally:
            response.close()
            response.release_conn()
        assert downloaded_hash == hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"file": filename, "rows": len(frame), "sha256": downloaded_hash,
                      "original_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                      "timestamp_timezone": "UTC"})
    save("prepare", {"redis_ping": True, "uploaded_files_verified": files})


def apply():
    result = subprocess.run([str(Path(sys.executable).parent / "feast"), "apply"], cwd=REPO, check=True, text=True, capture_output=True)
    print(result.stdout, flush=True)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    store = FeatureStore(repo_path=str(REPO))
    names = sorted(v.name for v in store.list_feature_views())
    assert names == sorted(SOURCES)
    s3().fput_object("feature-registry", "feature_store.yaml", str(REPO / "feature_store.yaml"))
    save("apply", {"feature_views": names, "redis_key_count": redis_client().dbsize(), "registry_bytes": s3().stat_object("feature-registry", "registry.db").size})


def samples():
    first = pd.read_parquet(DATA / SOURCES["demographic"][0]).head(5).copy()
    result = first[["user_id"]].copy()
    timestamps = []
    for filename, columns in SOURCES.values():
        frame = pd.read_parquet(DATA / filename)
        frame["feature_timestamp"] = pd.to_datetime(frame["feature_timestamp"], utc=True)
        latest = frame.sort_values("feature_timestamp").drop_duplicates("user_id", keep="last").set_index("user_id").loc[first.user_id]
        result = result.merge(latest[columns], on="user_id", validate="one_to_one")
        timestamps.extend(latest.feature_timestamp.tolist())
    result["event_timestamp"] = max(timestamps) + timedelta(seconds=1)
    return result


def verify_values(actual, expected):
    for _, columns in SOURCES.values():
        for column in columns:
            a = actual.set_index("user_id").loc[expected.user_id, column].tolist()
            b = expected[column].tolist()
            assert a == b, f"Source mismatch: {column}"


def historical():
    store = FeatureStore(repo_path=str(REPO))
    expected = samples()
    actual = store.get_historical_features(entity_df=expected[["user_id", "event_timestamp"]], features=FEATURES).to_df()
    verify_values(actual, expected)
    # A timestamp before all source records must not see future values.
    earliest = min(pd.to_datetime(pd.read_parquet(DATA / f).feature_timestamp, utc=True).min() for f, _ in SOURCES.values())
    before = expected[["user_id", "event_timestamp"]].copy()
    before["event_timestamp"] = earliest - timedelta(seconds=1)
    missing = store.get_historical_features(entity_df=before, features=FEATURES).to_df()
    columns = [c for _, cols in SOURCES.values() for c in cols]
    assert missing[columns].isna().all().all(), "Future values leaked into historical query"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    actual.to_csv(OUTPUT / "historical.csv", index=False)
    save("historical", {"users_checked": len(actual), "features_checked": len(FEATURES), "source_values_match": True, "before_source_timestamp_all_null": True})


def materialize():
    frames = [pd.read_parquet(DATA / f) for f, _ in SOURCES.values()]
    start = min(pd.to_datetime(d.feature_timestamp, utc=True).min() for d in frames) - timedelta(seconds=1)
    end = max(pd.to_datetime(d.feature_timestamp, utc=True).max() for d in frames) + timedelta(seconds=1)
    FeatureStore(repo_path=str(REPO)).materialize(start.to_pydatetime(), end.to_pydatetime())
    count = redis_client().dbsize()
    assert count > 0
    save("materialize", {"start": start.isoformat(), "end": end.isoformat(), "redis_key_count": count})


def online():
    expected = samples()
    actual = FeatureStore(repo_path=str(REPO)).get_online_features(entity_rows=expected[["user_id"]].to_dict("records"), features=FEATURES).to_df()
    verify_values(actual, expected)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    actual.to_csv(OUTPUT / "online.csv", index=False)
    save("online", {"users_checked": len(actual), "features_checked": len(FEATURES), "source_values_match": True, "redis_key_count": redis_client().dbsize()})


if __name__ == "__main__":
    steps = {"prepare": prepare, "apply": apply, "historical": historical, "materialize": materialize, "online": online}
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=[*steps, "all"])
    args = parser.parse_args()
    for name in (steps if args.step == "all" else [args.step]):
        print(f"\n=== {name} ===", flush=True)
        steps[name]()
