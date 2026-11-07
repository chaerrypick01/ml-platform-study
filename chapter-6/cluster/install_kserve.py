"""Install the pinned lab KServe components only into kind-ch5-lab."""

import json
from pathlib import Path
import subprocess
from urllib.request import urlretrieve

import yaml

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "chapter-6/.cache/kserve"
KUBECTL = ["kubectl", "--kubeconfig", str(ROOT / "chapter-5/.kube/config"),
           "--context", "kind-ch5-lab"]


def run(*args):
    subprocess.run([*KUBECTL, *args], check=True)


def download(name, url):
    path = CACHE / name
    if not path.exists():
        urlretrieve(url, path)
    return path


def main():
    config = json.loads(subprocess.check_output(
        [*KUBECTL, "config", "view", "--minify", "-o", "json"]
    ))
    if not config["clusters"][0]["cluster"]["server"].startswith("https://127.0.0.1:"):
        raise RuntimeError("Expected a local kind API endpoint")
    CACHE.mkdir(parents=True, exist_ok=True)
    cert = download("cert-manager-v1.17.2.yaml",
        "https://github.com/cert-manager/cert-manager/releases/download/v1.17.2/cert-manager.yaml")
    run("apply", "--server-side", "-f", str(cert))
    for name in ("cert-manager", "cert-manager-cainjector", "cert-manager-webhook"):
        run("-n", "cert-manager", "rollout", "status", f"deployment/{name}", "--timeout=180s")
    source = download("kserve-v0.15.2.yaml",
        "https://github.com/kserve/kserve/releases/download/v0.15.2/kserve.yaml")
    docs = list(yaml.safe_load_all(source.read_text()))
    for doc in docs:
        if not doc:
            continue
        name = doc.get("metadata", {}).get("name")
        if doc["kind"] == "ConfigMap" and name == "inferenceservice-config":
            doc["data"]["deploy"] = json.dumps({"defaultDeploymentMode": "RawDeployment"})
            ingress = json.loads(doc["data"]["ingress"])
            ingress.update(disableIngressCreation=True, disableIstioVirtualHost=True)
            doc["data"]["ingress"] = json.dumps(ingress)
        if doc["kind"] == "Deployment" and name == "kserve-localmodel-controller-manager":
            # This lab embeds a small model in its image; no node model cache needed.
            doc["spec"]["replicas"] = 0
    rendered = CACHE / "kserve-local.yaml"
    rendered.write_text(yaml.safe_dump_all(docs))
    run("apply", "--server-side", "-f", str(rendered))
    run("-n", "kserve", "rollout", "status", "deployment/kserve-controller-manager", "--timeout=180s")


if __name__ == "__main__":
    main()
