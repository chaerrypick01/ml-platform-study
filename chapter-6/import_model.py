"""Copy the trained pipeline from MLflow to the local BentoML model store."""

import os
from pathlib import Path

import bentoml
import mlflow

MODEL_URI = "models:/m-ca51f8c9ef8541adba6bcfe3eefceee7"

if __name__ == "__main__":
    mlflow.set_tracking_uri(
        os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001")
    )
    pipeline = mlflow.sklearn.load_model(MODEL_URI)
    saved = bentoml.sklearn.save_model(
        "income_pipeline",
        pipeline,
        signatures={"predict": {"batchable": False}},
        metadata={"mlflow_model_uri": MODEL_URI},
    )
    Path(__file__).with_name("model_tag.txt").write_text(f"{saved.tag}\n")
    print(f"Saved model: {saved.tag}")
    print(f"Model files: {saved.path}")
