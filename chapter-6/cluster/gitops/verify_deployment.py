"""Wait for the current deployment Git commit, then verify the actual serving Pod."""
import argparse
import json
from pathlib import Path
import subprocess
import time

import yaml

CHAPTER = Path(__file__).resolve().parents[2]
KUBE = ["kubectl", "--kubeconfig", str(CHAPTER.parent / "chapter-5/.kube/config"),
        "--context", "kind-ch5-lab"]


def command(*args):
    return subprocess.check_output([*KUBE, *args], text=True)


def verify(timeout=180):
    revision = subprocess.check_output(["git", "--git-dir", str(CHAPTER / ".cache/gitops/remote.git"),
                                        "rev-parse", "main"], text=True).strip()
    raw = subprocess.check_output(["git", "--git-dir", str(CHAPTER / ".cache/gitops/remote.git"),
                                   "show", "main:income-service.yaml"], text=True)
    spec = next(d for d in yaml.safe_load_all(raw) if d["kind"] == "InferenceService")
    expected = spec["spec"]["predictor"]["containers"][0]
    command("annotate", "applications.argoproj.io", "ch6-income", "-n", "argocd",
            "argocd.argoproj.io/refresh=hard", "--overwrite")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app = json.loads(command("get", "applications.argoproj.io", "ch6-income", "-n", "argocd", "-o", "json"))
        deploy = json.loads(command("get", "deploy", "income-classifier-predictor", "-n", "ch6-serving", "-o", "json"))
        sync = app.get("status", {}).get("sync", {})
        containers = deploy["spec"]["template"]["spec"]["containers"]
        actual = next(c for c in containers if c["name"] == "kserve-container")
        if sync.get("revision") == revision and sync.get("status") == "Synced" and actual["image"] == expected["image"] and actual.get("env") == expected.get("env"):
            break
        time.sleep(2)
    else:
        raise TimeoutError(f"Git revision {revision} was not fully reconciled")
    command("rollout", "status", "deployment/income-classifier-predictor", "-n", "ch6-serving", f"--timeout={timeout}s")
    release = command("exec", "-n", "ch6-serving", "deployment/income-classifier-predictor", "--", "printenv", "CH6_RELEASE").strip()
    assert release == next(e["value"] for e in expected["env"] if e["name"] == "CH6_RELEASE")
    sample = (CHAPTER / "sample_request.json").read_text()
    code = ("import json,urllib.request; "
            f"r=urllib.request.Request('http://127.0.0.1:3000/predict',data={sample!r}.encode(),headers={{'Content-Type':'application/json'}}); "
            "v=json.load(urllib.request.urlopen(r,timeout=20)); assert v['prediction']==0; print(json.dumps(v))")
    result = json.loads(command("exec", "-n", "ch6-serving", "deployment/income-classifier-predictor", "--", "python", "-c", code))
    evidence = {"deployment_revision": revision, "image": expected["image"], "release": release, "prediction": result}
    print(json.dumps(evidence, indent=2))
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    verify(args.timeout)
