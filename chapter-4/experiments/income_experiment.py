"""Run a reproducible income classification comparison with local MLflow tracking."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, average_precision_score, ConfusionMatrixDisplay,
    f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "experiments" / "outputs"
TRACKING_URI = f"sqlite:///{OUTPUTS / 'mlflow.db'}"
EXPERIMENT_NAME = "assignment-income-classification"
SEED = 42


def evaluate(model, X, y):
    predicted = model.predict(X)
    positive_index = list(model.classes_).index(1)
    probability = model.predict_proba(X)[:, positive_index]
    return {
        "accuracy": accuracy_score(y, predicted),
        "roc_auc": roc_auc_score(y, probability),
        "average_precision": average_precision_score(y, probability),
        "precision": precision_score(y, predicted, zero_division=0),
        "recall": recall_score(y, predicted, zero_division=0),
        "f1": f1_score(y, predicted, zero_division=0),
    }


def run_experiment():
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = OUTPUTS / batch_id
    destination.mkdir()
    data_path = ROOT / "data" / "income_data.csv"
    data = pd.read_csv(data_path, skipinitialspace=True)
    for column in data.select_dtypes(include="object"):
        data[column] = data[column].str.strip()
    assert not data.isna().any().any(), "Review missing values before training."
    assert set(data.Target.unique()) == {"<=50K", ">50K"}
    X = data.drop(columns="Target")
    y = (data.Target == ">50K").astype(int)
    train_valid, test = train_test_split(
        data.index, test_size=0.2, stratify=y, random_state=SEED
    )
    train, valid = train_test_split(
        train_valid, test_size=0.25, stratify=y.loc[train_valid], random_state=SEED
    )
    assert not (set(train) & set(valid) or set(train) & set(test) or set(valid) & set(test))
    manifest = {
        "seed": SEED,
        "data_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
        "rows": len(data), "positive_label": ">50K",
        "positive_fraction": float(y.mean()),
        "split_sizes": {"train": len(train), "validation": len(valid), "test": len(test)},
        "selection_metric": "validation_roc_auc",
        "python": sys.version,
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2))
    split_rows = pd.concat([
        pd.DataFrame({"row_index": indices, "split": name})
        for name, indices in [("train", train), ("validation", valid), ("test", test)]
    ])
    split_rows.to_csv(destination / "split_rows.csv", index=False)
    packages = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    (destination / "requirements-lock.txt").write_text(packages)

    mlflow.set_tracking_uri(TRACKING_URI)
    experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
    experiment_id = experiment.experiment_id if experiment else mlflow.create_experiment(
        EXPERIMENT_NAME, artifact_location=(OUTPUTS / "artifacts").as_uri()
    )
    candidates = {
        "dummy_most_frequent": DummyClassifier(strategy="most_frequent"),
        "decision_tree_depth5": DecisionTreeClassifier(max_depth=5, random_state=SEED),
        "decision_tree_unlimited": DecisionTreeClassifier(random_state=SEED),
        "random_forest": RandomForestClassifier(
            n_estimators=150, max_depth=12, min_samples_leaf=2, random_state=SEED, n_jobs=2
        ),
    }
    rows = []
    for name, estimator in candidates.items():
        # Fit preprocessing only on training data; preserve it with the estimator.
        model = Pipeline([("encoder", OneHotEncoder(handle_unknown="ignore")), ("classifier", estimator)])
        with mlflow.start_run(experiment_id=experiment_id, run_name=f"{batch_id}-{name}") as run:
            mlflow.set_tags({"batch_id": batch_id, "phase": "candidate"})
            mlflow.log_params({"model": name, "seed": SEED, "data_sha256": manifest["data_sha256"]})
            mlflow.log_params(estimator.get_params())
            started = time.perf_counter()
            model.fit(X.loc[train], y.loc[train])
            metrics = {"fit_seconds": time.perf_counter() - started}
            for split, indices in [("train", train), ("validation", valid)]:
                metrics.update({f"{split}_{key}": value for key, value in evaluate(model, X.loc[indices], y.loc[indices]).items()})
            mlflow.log_metrics(metrics)
            mlflow.log_artifact(str(destination / "manifest.json"))
            rows.append({"model": name, "run_id": run.info.run_id, **metrics})
            print(name, "validation ROC AUC:", round(metrics["validation_roc_auc"], 4), flush=True)

    comparison = pd.DataFrame(rows).sort_values("validation_roc_auc", ascending=False)
    comparison.to_csv(destination / "comparison.csv", index=False)
    winner = comparison.iloc[0]["model"]
    final_model = Pipeline([
        ("encoder", OneHotEncoder(handle_unknown="ignore")),
        ("classifier", clone(candidates[winner])),
    ])
    # Choose on validation only; refit with train+validation, then evaluate the held-out test.
    final_model.fit(X.loc[train_valid], y.loc[train_valid])
    test_metrics = evaluate(final_model, X.loc[test], y.loc[test])
    with mlflow.start_run(experiment_id=experiment_id, run_name=f"{batch_id}-final-{winner}") as run:
        mlflow.set_tags({"batch_id": batch_id, "phase": "final"})
        mlflow.log_params({"selected_model": winner, "seed": SEED, "selection_metric": "validation_roc_auc"})
        mlflow.log_metrics({f"test_{key}": value for key, value in test_metrics.items()})
        model_info = mlflow.sklearn.log_model(
            final_model, artifact_path="model", input_example=X.loc[test].head(3),
            registered_model_name="assignment-income-classifier",
        )
        # Verify the serialized model can be loaded and gives identical predictions.
        loaded = mlflow.sklearn.load_model(model_info.model_uri)
        np.testing.assert_array_equal(loaded.predict(X.loc[test]), final_model.predict(X.loc[test]))
        fig, ax = plt.subplots(figsize=(5, 4))
        ConfusionMatrixDisplay.from_estimator(final_model, X.loc[test], y.loc[test], display_labels=["<=50K", ">50K"], ax=ax)
        fig.tight_layout()
        fig.savefig(destination / "test_confusion_matrix.png")
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(8, 4))
        comparison.set_index("model")[["train_roc_auc", "validation_roc_auc"]].plot.bar(ax=ax)
        ax.set_ylim(0, 1)
        ax.set_ylabel("ROC AUC")
        fig.tight_layout()
        fig.savefig(destination / "model_comparison.png")
        plt.close(fig)
        result = {
            **manifest, "batch_id": batch_id, "selected_model": winner,
            "test_metrics": test_metrics, "final_run_id": run.info.run_id,
            "model_uri": model_info.model_uri, "reload_predictions_match": True,
        }
        (destination / "result.json").write_text(json.dumps(result, indent=2))
        mlflow.log_artifacts(str(destination))
        mlflow.log_artifact(__file__, artifact_path="source")
    print(comparison[["model", "train_roc_auc", "validation_roc_auc"]].to_string(index=False))
    print("Final test metrics:", json.dumps(test_metrics, indent=2))
    print("Results:", destination)
    return destination


if __name__ == "__main__":
    run_experiment()
