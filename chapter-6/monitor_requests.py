"""Tail a fresh lab request log and evaluate non-overlapping request windows."""

import argparse
import json
import time
from pathlib import Path

import pandas as pd
from report_drift import evaluate
from drift_alerts import feature_alerts, append_alerts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-log", type=Path, required=True)
    parser.add_argument("--window-size", type=int, default=1000)
    parser.add_argument("--windows", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    if min(args.window_size, args.windows, args.timeout) <= 0:
        parser.error("window-size, windows, and timeout must be positive")
    folder = args.request_log.parent
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / "window_001.json").exists() or (folder / "alerts.jsonl").exists():
        parser.error("Reports already exist; use a new request-log directory")
    reference = pd.read_csv(Path(__file__).parent / "outputs/drift/reference.csv")
    deadline = time.monotonic() + args.timeout
    while not args.request_log.exists():
        if time.monotonic() > deadline:
            raise TimeoutError("No request log received")
        time.sleep(0.2)
    batch = []
    completed = 0
    with args.request_log.open() as stream:
        while completed < args.windows:
            position = stream.tell()
            line = stream.readline()
            if not line.endswith("\n"):
                stream.seek(position)
                if time.monotonic() > deadline:
                    raise TimeoutError(f"Only {completed} full windows received")
                time.sleep(0.2)
                continue
            batch.append(json.loads(line))
            if len(batch) < args.window_size:
                continue
            completed += 1
            current = pd.DataFrame([record["features"] for record in batch])
            result = evaluate(current, reference)
            prefix = folder / f"window_{completed:03d}"
            result.save_html(str(prefix.with_suffix(".html")))
            result.save_json(str(prefix.with_suffix(".json")))
            current.to_csv(prefix.with_suffix(".csv"), index=False)
            alerts = feature_alerts(result.dict(), prefix.with_suffix(".json"))
            append_alerts(alerts, folder / "alerts.jsonl")
            drifted = [alert["feature"] for alert in alerts]
            print(f"Window {completed}: {len(batch)} requests; drift={drifted}", flush=True)
            print(f"Report: {prefix.with_suffix('.html')}", flush=True)
            batch.clear()


if __name__ == "__main__":
    main()
