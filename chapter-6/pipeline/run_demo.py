"""Compile and execute real KFP conditional runs for current and shifted batches."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import kfp
from kfp import compiler, dsl

CHAPTER = Path(__file__).resolve().parents[1]


def pipeline_for(image):
    @dsl.container_component
    def gate(batch: str, model_tag: str, allow: dsl.OutputPath(bool), report: dsl.Output[dsl.Artifact]):
        return dsl.ContainerSpec(image=image, command=["python", "/app/gate.py"],
            args=["gate", "--batch", batch, "--model-tag", model_tag, "--allow", allow, "--output", report.path])

    @dsl.container_component
    def infer(batch: str, endpoint: str, predictions: dsl.Output[dsl.Dataset]):
        return dsl.ContainerSpec(image=image, command=["python", "/app/gate.py"],
            args=["infer", "--batch", batch, "--endpoint", endpoint, "--output", predictions.path])

    @dsl.container_component
    def skip(reason: dsl.Output[dsl.Artifact]):
        return dsl.ContainerSpec(image=image, command=["python", "/app/gate.py"],
            args=["skip", "--output", reason.path])

    @dsl.pipeline(name="chapter6-drift-gated-inference")
    def pipeline(batch: str, model_tag: str,
                 endpoint: str = "http://income-classifier-predictor.ch6-serving.svc.cluster.local"):
        decision = gate(batch=batch, model_tag=model_tag)
        with dsl.If(decision.outputs["allow"] == True, name="no-critical-drift"):
            prediction = infer(batch=batch, endpoint=endpoint)
        with dsl.Else(name="critical-drift"):
            skipped = skip()
        for task in (decision, prediction, skipped):
            task.set_caching_options(False)
            task.set_cpu_request("100m").set_memory_request("256Mi").set_memory_limit("1Gi")
    return pipeline


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kfp-endpoint", default="http://127.0.0.1:8082")
    args = parser.parse_args()
    image = (CHAPTER / ".cache/gate-image.txt").read_text().strip()
    out = CHAPTER / "outputs" / datetime.now(timezone.utc).strftime("kfp-gate-%Y%m%dT%H%M%S")
    out.mkdir(parents=True)
    package = out / "pipeline.yaml"
    compiler.Compiler().compile(pipeline_func=pipeline_for(image), package_path=str(package))
    client = kfp.Client(host=args.kfp_endpoint)
    records = []
    for batch in ("current", "shifted"):
        run = client.create_run_from_pipeline_package(str(package),
            arguments={"batch": batch, "model_tag": (CHAPTER / "model_tag.txt").read_text().strip()},
            run_name=f"ch6-gate-{batch}-{out.name}", experiment_name="chapter-6", enable_caching=False)
        records.append({"batch": batch, "run_id": run.run_id})
        (out / "runs.json").write_text(json.dumps(records, indent=2))
        print(f"Submitted {batch}: {run.run_id}", flush=True)
    for record in records:
        result = client.wait_for_run_completion(record["run_id"], timeout=600, sleep_duration=5)
        data = result.to_dict()
        (out / f"{record['batch']}.json").write_text(json.dumps(data, indent=2, default=str))
        assert result.state == "SUCCEEDED", f"{record['batch']} failed: inspect {out / (record['batch'] + '.json')}"
        tasks = data["run_details"]["task_details"]
        names = {task["display_name"] for task in tasks if task["state"] == "SUCCEEDED"}
        if record["batch"] == "current":
            assert "infer" in names and "skip" not in names, names
        else:
            assert "skip" in names and "infer" not in names, names
        record.update(state=result.state, succeeded_tasks=sorted(names))
        print(record, flush=True)
    (out / "runs.json").write_text(json.dumps(records, indent=2))
    print(f"Verified conditional execution: {out}")
