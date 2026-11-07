"""Local trusted-code CI runner invoked by source.git/hooks/post-receive.

Stages: checkout -> unit tests -> Bento/image build -> HTTP smoke -> push -> GitOps.
The hook runs synchronously. A failed job leaves the deployed Git image unchanged.
"""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

import yaml

CHAPTER = Path(__file__).resolve().parents[1]
CACHE = CHAPTER / ".cache/ci"
PYTHON = CHAPTER / ".venv/bin/python"
BENTO = CHAPTER / ".venv/bin/bentoml"


def execute(revision):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    version = f"ci-{revision[:12]}-{stamp}"
    job = CACHE / "jobs" / version
    job.mkdir(parents=True)
    # BentoML refuses build contexts below hidden directories such as .cache.
    source = CHAPTER / "outputs/ci-build" / version
    source.parent.mkdir(parents=True, exist_ok=True)
    record = {"source_revision": revision, "version": version, "status": "RUNNING"}
    image = f"localhost:5002/ch6-income:{version}"
    container = f"ch6-smoke-{stamp}"
    # Git hooks inherit repository-local environment. Never leak it into another repo.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(BENTOML_DO_NOT_TRACK="True", PYTHONPATH=str(source))
    with (job / "job.log").open("w") as log:
        def run(*args, capture=False, cwd=source):
            print("$ " + " ".join(map(str, args)), file=log, flush=True)
            return subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True,
                                  text=True, stdout=subprocess.PIPE if capture else log, stderr=log)
        try:
            run("git", "clone", "--no-local", "--no-checkout", CACHE / "source.git", source, cwd=CHAPTER)
            run("git", "checkout", "--detach", revision)
            record["stage"] = "unit_tests"
            run(PYTHON, "-m", "unittest", "test_service")
            record["stage"] = "build"
            run(BENTO, "build", "--platform", "aarch64-manylinux_2_36", "--version", version)
            run(BENTO, "containerize", f"income_service:{version}", "-t", image,
                "--opt", "platform=linux/arm64", "--opt", "progress=plain")
            record["stage"] = "container_smoke"
            run("docker", "run", "-d", "--name", container, "-p", "127.0.0.1::3000",
                "-e", "BENTOML_DO_NOT_TRACK=True", "-e", "CH6_LOG_STDOUT=1",
                "-e", "CH6_REQUEST_LOG=/proc/ch6-forbidden/requests.jsonl", image, "serve")
            info = json.loads(run("docker", "inspect", container, capture=True).stdout)[0]
            port = info["NetworkSettings"]["Ports"]["3000/tcp"][0]["HostPort"]
            endpoint = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 90
            while True:
                try:
                    with urlopen(endpoint + "/readyz", timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    if time.monotonic() > deadline:
                        raise TimeoutError("Smoke container did not become ready")
                    time.sleep(1)
            run(PYTHON, "smoke.py", "--endpoint", endpoint)
            time.sleep(1)
            logs = subprocess.check_output(["docker", "logs", container], stderr=subprocess.STDOUT, text=True)
            (job / "smoke.log").write_text(logs)
            assert "Request log write failed" in logs, "Failure injection was not exercised"
            assert "CH6_REQUEST " in logs, "Structured request logging did not run"
            run("docker", "rm", "-f", container)
            record["stage"] = "push_image"
            run("docker", "push", image)
            image_info = json.loads(run("docker", "image", "inspect", image, capture=True).stdout)[0]
            pinned = next(x for x in image_info["RepoDigests"] if x.startswith("localhost:5002/ch6-income@"))
            record["image"] = pinned
            manifest = CHAPTER / "cluster/gitops/income-service.yaml"
            record["previous_manifest"] = manifest.read_text()
            docs = list(yaml.safe_load_all(record["previous_manifest"]))
            serving = next(x for x in docs if x["kind"] == "InferenceService")
            container_spec = serving["spec"]["predictor"]["containers"][0]
            record["previous_image"] = container_spec["image"]
            container_spec["image"] = pinned
            values = {x["name"]: x["value"] for x in container_spec.get("env", [])}
            values.update(CH6_RELEASE=version, CH6_LOG_STDOUT="1")
            container_spec["env"] = [{"name": k, "value": v} for k, v in values.items()]
            record["manifest"] = yaml.safe_dump_all(docs, sort_keys=False)
            record["stage"] = "publish_gitops"
            manifest.write_text(record["manifest"])
            run(PYTHON, CHAPTER / "cluster/gitops/publish.py", "--message",
                f"Deploy tested image for source {revision[:12]}", cwd=CHAPTER)
            record["deployment_revision"] = run("git", "rev-parse", "HEAD", capture=True,
                cwd=CHAPTER / ".cache/gitops/work").stdout.strip()
            record["status"] = "SUCCEEDED"
        except Exception as error:
            record.update(status="FAILED", error=str(error))
            print(f"FAILED: {error}", file=log)
            subprocess.run(["docker", "rm", "-f", container], stdout=log, stderr=log)
        finally:
            (job / "result.json").write_text(json.dumps(record, indent=2) + "\n")
            (CACHE / "latest.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"CI {record['status']}: {job}", flush=True)
    return record["status"] == "SUCCEEDED"


if __name__ == "__main__":
    updates = [line.split() for line in sys.stdin if line.strip()]
    with (CACHE / "runner.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for old, new, ref in updates:
            if ref == "refs/heads/main" and new != "0" * 40:
                if not execute(new):
                    raise SystemExit(1)
