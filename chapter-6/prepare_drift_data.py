"""Prepare reference, unchanged current, and shifted current feature batches."""

import hashlib
import json
from pathlib import Path

import pandas as pd


def main():
    root = Path(__file__).resolve().parent
    chapter4 = root.parent / "chapter-4"
    result = json.loads((chapter4 / "experiments/results/result.json").read_text())
    source = chapter4 / "data/income_data.csv"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != result["data_sha256"]:
        raise ValueError("Source CSV differs from the recorded training data.")
    splits = pd.read_csv(
        chapter4 / "experiments/outputs" / result["batch_id"] / "split_rows.csv"
    )
    if not splits.row_index.is_unique:
        raise ValueError("Recorded splits contain overlapping row indices.")
    data = pd.read_csv(source, skipinitialspace=True)
    for column in data.select_dtypes(include="object"):
        data[column] = data[column].str.strip()
    features = data.drop(columns="Target")

    # The final model was refit on train + validation, not train alone.
    training_indices = splits.loc[
        splits.split.isin(["train", "validation"]), "row_index"
    ]
    test_indices = splits.loc[splits.split == "test", "row_index"]
    reference = features.loc[training_indices].sample(n=1000, random_state=42)
    current = features.loc[test_indices].sample(n=1000, random_state=42)
    shifted = current.copy()
    changed_indices = shifted.sample(frac=0.8, random_state=42).index
    shifted.loc[changed_indices, "Education"] = "Masters"

    out = root / "outputs/drift"
    out.mkdir(parents=True, exist_ok=True)
    batches = {"reference": reference, "current": current, "shifted": shifted}
    for name, frame in batches.items():
        frame.to_csv(out / f"{name}.csv", index=False)
    pd.DataFrame({"reference_row": reference.index, "current_row": current.index}).to_csv(
        out / "source_rows.csv", index=False
    )
    metadata = {
        "source_sha256": digest,
        "model_uri": result["model_uri"],
        "seed": 42,
        "rows_per_batch": 1000,
        "reference_source": "train + validation used to refit the final model",
        "current_source": "held-out test rows; simulated production input",
        "shift": "assign Masters to Education in 80% of current rows",
        "actually_changed_rows": int((current.Education != shifted.Education).sum()),
        "note": "Synthetic input shift; labels omitted; no accuracy claim.",
    }
    (out / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    proportions = pd.DataFrame({
        name: frame.Education.value_counts(normalize=True).mul(100)
        for name, frame in batches.items()
    }).fillna(0).round(1)
    print("Education distribution (%)")
    print(proportions.sort_values("reference", ascending=False).to_string())
    print(f"\nRows per batch: 1000; features: {len(features.columns)}")
    print(f"Actually changed Education rows: {metadata['actually_changed_rows']}")
    print(f"Saved to: {out}")


if __name__ == "__main__":
    main()
