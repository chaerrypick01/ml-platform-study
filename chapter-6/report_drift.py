"""Generate local Evidently reports for the two prepared comparisons."""

import os
from pathlib import Path

os.environ.setdefault("DO_NOT_TRACK", "1")

import pandas as pd
from evidently import DataDefinition, Dataset, Report
from evidently.presets import DataDriftPreset


def evaluate(current_frame, reference_frame):
    if list(current_frame.columns) != list(reference_frame.columns):
        raise ValueError("Reference and current schemas differ.")
    definition = DataDefinition(categorical_columns=list(reference_frame.columns))
    reference = Dataset.from_pandas(reference_frame, data_definition=definition)
    current = Dataset.from_pandas(current_frame, data_definition=definition)
    report = Report([
        DataDriftPreset(cat_method="jensenshannon", cat_threshold=0.1, drift_share=0.5)
    ], include_tests=True)
    return report.run(current, reference)


def main():
    folder = Path(__file__).resolve().parent / "outputs/drift"
    reference_frame = pd.read_csv(folder / "reference.csv")
    for name in ("current", "shifted"):
        current_frame = pd.read_csv(folder / f"{name}.csv")
        result = evaluate(current_frame, reference_frame)
        result.save_html(str(folder / f"{name}_report.html"))
        result.save_json(str(folder / f"{name}_report.json"))
        print(f"{name}: {folder / f'{name}_report.html'}")
        for metric in result.dict()["metrics"]:
            config = metric["config"]
            if "column" in config:
                score = metric["value"]
                detected = score >= config["threshold"]
                print(f"  {config['column']:16} score={score:.3f} drift={detected}")


if __name__ == "__main__":
    main()
