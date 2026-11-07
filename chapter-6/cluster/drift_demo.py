"""Collect real Kubernetes request logs, then evaluate two fixed windows off-path."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import Request, urlopen

import pandas as pd

CHAPTER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CHAPTER))
from report_drift import evaluate
from drift_alerts import feature_alerts, append_alerts

KUBE = ["kubectl", "--kubeconfig", str(CHAPTER.parent / "chapter-5/.kube/config"),
        "--context", "kind-ch5-lab"]


def kube(*args):
    return subprocess.check_output([*KUBE, *args], text=True)


def predict(endpoint, features):
    request = Request(endpoint + "/predict", data=json.dumps({"features": features}).encode(),
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
        assert result["prediction"] in (0, 1)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:3004")
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = CHAPTER / "outputs" / f"cluster-{stamp}"
    out.mkdir(parents=True)
    pods = json.loads(kube("get", "pods", "-n", "ch6-serving", "-o", "json"))["items"]
    pods = [p for p in pods if not p["metadata"].get("deletionTimestamp")]
    assert len(pods) == 1, "This single-replica lab requires one stable serving Pod"
    pod = pods[0]
    pod_name = pod["metadata"]["name"]
    # Count baseline log records so other prior exercises don't enter this window.
    def records():
        lines = kube("logs", "-n", "ch6-serving", pod_name).splitlines()
        # Bento access logs can share a line with stdout; decode the JSON object
        # rather than treating trailing access-log text as part of the record.
        decoder = json.JSONDecoder()
        return [decoder.raw_decode(line.split("CH6_REQUEST ", 1)[1])[0]
                for line in lines if "CH6_REQUEST " in line]
    before = len(records())
    folder = CHAPTER / "outputs/drift"
    frames = [pd.read_csv(folder / f"{name}.csv") for name in ("current", "shifted")]
    for name, frame in zip(("current", "shifted"), frames):
        for row in frame.to_dict(orient="records"):
            predict(args.endpoint, row)
        print(f"{name}: sent {len(frame)} requests", flush=True)
    deadline = time.monotonic() + 30
    while True:
        received = records()[before:]
        if len(received) >= 2000:
            break
        if time.monotonic() > deadline:
            raise TimeoutError(f"Expected 2000 logs; received {len(received)} (possible drops/rotation)")
        time.sleep(1)
    assert len(received) == 2000, "Concurrent traffic mixed with this controlled experiment"
    model_tag = (CHAPTER / "model_tag.txt").read_text().strip()
    assert {r["model_tag"] for r in received} == {model_tag}, "Reference/model version mismatch"
    origin = json.loads((folder / "manifest.json").read_text())
    assert {r["model_uri"] for r in received} == {origin["model_uri"]}, "Reference belongs to another trained model"
    actual = pd.DataFrame([r["features"] for r in received])
    expected = pd.concat(frames, ignore_index=True)
    pd.testing.assert_frame_equal(actual[expected.columns], expected)
    reference = pd.read_csv(folder / "reference.csv")
    alerts = []
    for index in range(2):
        current = actual.iloc[index * 1000:(index + 1) * 1000][reference.columns]
        report = evaluate(current, reference)
        path = out / f"window_{index + 1:03d}.json"
        report.save_json(str(path))
        report.save_html(str(path.with_suffix(".html")))
        current.to_csv(path.with_suffix(".csv"), index=False)
        batch_alerts = feature_alerts(report.dict(), path)
        assert {a["feature"] for a in batch_alerts} == ({"Native_country"} if index == 0 else {"Native_country", "Education"})
        append_alerts(batch_alerts, out / "alerts.jsonl")
        alerts.extend(batch_alerts)
    (out / "requests.jsonl").write_text("".join(json.dumps(r) + "\n" for r in received))
    # Exercise a broken monitor input without touching the predictor process.
    try:
        evaluate(frames[0], reference.drop(columns="Education"))
    except ValueError:
        monitor_failure = "reference schema mismatch"
    else:
        raise AssertionError("Expected the monitor's schema check to fail")
    after_failure = predict(args.endpoint, frames[0].iloc[0].to_dict())
    metadata = {"pod": pod_name, "pod_uid": pod["metadata"]["uid"],
        "image": pod["spec"]["containers"][0]["image"], "model_tag": model_tag,
        "reference_sha256": hashlib.sha256((folder / "reference.csv").read_bytes()).hexdigest(),
        "reference_origin": origin,
        "rows": len(received), "alerts": len(alerts),
        "injected_monitor_failure": monitor_failure, "prediction_after_monitor_failure": after_failure,
        "limitations": "Controlled sequential traffic; one stable Pod; no rotation, persistent collector or log loss recovery"}
    (out / "manifest.json").write_text(json.dumps(metadata, indent=2))
    print(f"Verified 2000 requests, 3 alerts, prediction after monitor failure: {out}")


if __name__ == "__main__":
    main()
