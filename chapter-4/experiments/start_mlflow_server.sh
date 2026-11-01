#!/usr/bin/env bash
# Start the MLflow tracking server for the income experiment (run from chapter-4).
#
#   client --HTTP--> tracking server --SQL--> backend store  (SQLite: experiments/outputs/mlflow.db)
#                                    --S3---> artifact store (MinIO: s3://mlflow-artifacts)
#
# Only this server holds the MinIO credentials; experiment code talks HTTP only.
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${MLFLOW_PORT:-5001}"
OUTPUTS="$(pwd)/experiments/outputs"
mkdir -p "$OUTPUTS"

# Loopback-only credentials of the tutorial MinIO in experiments/feature_store/compose.yaml.
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-ch4local}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-ch4-local-only-password}"
export MLFLOW_S3_ENDPOINT_URL="${MLFLOW_S3_ENDPOINT_URL:-http://127.0.0.1:19000}"

# The server writes into an existing bucket; create it once if missing.
venv/bin/python - <<'PY'
import os, sys
from urllib.parse import urlparse
from minio import Minio

endpoint = urlparse(os.environ["MLFLOW_S3_ENDPOINT_URL"])
client = Minio(endpoint.netloc, access_key=os.environ["AWS_ACCESS_KEY_ID"],
               secret_key=os.environ["AWS_SECRET_ACCESS_KEY"], secure=endpoint.scheme == "https")
try:
    if not client.bucket_exists("mlflow-artifacts"):
        client.make_bucket("mlflow-artifacts")
except Exception as error:
    sys.exit(f"MinIO에 연결할 수 없습니다 ({error}). 먼저 실행하세요: "
             "docker compose -f experiments/feature_store/compose.yaml up -d --wait")
PY

exec venv/bin/mlflow server \
  --backend-store-uri "sqlite:///$OUTPUTS/mlflow.db" \
  --artifacts-destination "s3://mlflow-artifacts" \
  --host 127.0.0.1 --port "$PORT"
