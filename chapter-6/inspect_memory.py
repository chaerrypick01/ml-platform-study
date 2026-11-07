"""Compare model file size and RSS in a fresh local process (MiB)."""

from pathlib import Path

import bentoml
import pandas as pd
import psutil
import sklearn  # Load the framework before measuring the baseline.


def rss_mib():
    return psutil.Process().memory_info().rss / 1024**2


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    tag = (root / "model_tag.txt").read_text().strip()
    stored = bentoml.sklearn.get(tag)
    file_size = Path(stored.path_of("saved_model.pkl")).stat().st_size / 1024**2
    before = rss_mib()
    model = bentoml.sklearn.load_model(stored)
    after_load = rss_mib()
    import json

    payload = json.loads((root / "sample_request.json").read_text())
    prediction = model.predict(pd.DataFrame([payload["features"]]))
    after_predict = rss_mib()
    print(f"Model file: {file_size:.1f} MiB")
    print(f"RSS before loading: {before:.1f} MiB")
    print(f"RSS after loading: {after_load:.1f} MiB")
    print(f"Loading RSS increase: {after_load - before:.1f} MiB")
    print(f"RSS after prediction: {after_predict:.1f} MiB")
    print(f"Prediction: {prediction.tolist()}")
    print("RSS includes Python and libraries; the increase is not model-only memory.")
