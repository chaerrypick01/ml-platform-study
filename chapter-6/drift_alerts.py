"""Convert Evidently feature drift failures into local review alerts."""

import argparse
import json
from pathlib import Path


def feature_alerts(report, report_path):
    metrics = {item["id"]: item for item in report["metrics"]}
    alerts = []
    for test in report["tests"]:
        if test["id"] != "drift" or test["status"] != "FAIL":
            continue
        metric = metrics[test["metric_config"]["metric_id"]]
        config = metric["config"]
        alerts.append({
            "window": report_path.stem,
            "feature": config["column"],
            "method": config["method"],
            "score": metric["value"],
            "threshold": config["threshold"],
            "severity": "warning",
            "action": "review_data_change",
            "report": str(report_path.with_suffix(".html").resolve()),
        })
    return alerts


def append_alerts(alerts, output):
    with output.open("a") as stream:
        for alert in alerts:
            stream.write(json.dumps(alert) + "\n")
            print(
                f"WARNING {alert['window']} {alert['feature']}: "
                f"score={alert['score']:.3f}, threshold={alert['threshold']:.3f}; "
                "review_data_change",
                flush=True,
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report_dir", type=Path)
    args = parser.parse_args()
    reports = sorted(args.report_dir.glob("window_*.json"))
    if not reports:
        parser.error("No window_*.json reports found")
    # Rebuild the derived alert file instead of duplicating alerts on rerun.
    all_alerts = []
    for path in reports:
        all_alerts.extend(feature_alerts(json.loads(path.read_text()), path))
    output = args.report_dir / "alerts.jsonl"
    output.write_text("")
    append_alerts(all_alerts, output)
    print(f"Saved {len(all_alerts)} alerts: {output}")


if __name__ == "__main__":
    main()
