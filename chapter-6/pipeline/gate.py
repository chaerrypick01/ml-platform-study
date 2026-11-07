"""Container entrypoint for the KFP drift gate and conditional API inference."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
from report_drift import evaluate

DATA = Path("/app/data")


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["gate", "infer", "skip"])
    parser.add_argument("--batch", choices=["current", "shifted"], default="current")
    parser.add_argument("--model-tag")
    parser.add_argument("--allow")
    parser.add_argument("--output", required=True)
    parser.add_argument("--endpoint")
    args = parser.parse_args()
    if args.action == "gate":
        model_tag = (DATA / "model_tag.txt").read_text().strip()
        if args.model_tag != model_tag:
            raise ValueError("Reference/model tag mismatch; refusing inference")
        reference = pd.read_csv(DATA / "reference.csv")
        current = pd.read_csv(DATA / f"{args.batch}.csv")
        result = evaluate(current, reference)
        metrics = {m["config"]["column"]: m for m in result.dict()["metrics"] if "column" in m["config"]}
        score = float(metrics["Education"]["value"])
        # Explicit lab policy: Education blocks inference; other feature drifts warn.
        allow = bool(score < 0.1)
        report = {"batch": args.batch, "allow_inference": allow, "critical_feature": "Education",
            "score": score, "threshold": 0.1, "model_tag": model_tag,
            "reference_sha256": hashlib.sha256((DATA / "reference.csv").read_bytes()).hexdigest(),
            "reference_origin": json.loads((DATA / "manifest.json").read_text()),
            "evidently": result.dict()}
        write(args.output, json.dumps(report, default=str))
        write(args.allow, json.dumps(allow))
        print(f"Education JS={score:.6f}; allow_inference={allow}")
    elif args.action == "infer":
        predictions = []
        for row in pd.read_csv(DATA / f"{args.batch}.csv").head(10).to_dict(orient="records"):
            request = Request(args.endpoint + "/predict", data=json.dumps({"features": row}).encode(),
                              headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=30) as response:
                predictions.append(json.load(response))
        write(args.output, json.dumps({"rows": len(predictions), "predictions": predictions}))
        print(f"INFERENCE_EXECUTED: {len(predictions)} real API requests")
    else:
        write(args.output, json.dumps({"action": "skip_inference", "reason": "Education drift exceeded 0.1"}))
        print("INFERENCE_SKIPPED: no prediction requests sent")


if __name__ == "__main__":
    main()
