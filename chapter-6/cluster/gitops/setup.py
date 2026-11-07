"""Install pinned Argo CD and connect the separate local GitOps repository."""
import json
from pathlib import Path
import subprocess
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "chapter-6/.cache"
KUBE = ["kubectl", "--kubeconfig", str(ROOT / "chapter-5/.kube/config"),
        "--context", "kind-ch5-lab"]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def main():
    config = json.loads(subprocess.check_output([*KUBE, "config", "view", "--minify", "-o", "json"]))
    if not config["clusters"][0]["cluster"]["server"].startswith("https://127.0.0.1:"):
        raise RuntimeError("Expected the local kind API endpoint")
    remote = CACHE / "gitops/remote.git"
    if not remote.exists():
        raise RuntimeError("Run publish.py first to create the local Git repository")
    install = CACHE / "argocd/install-v3.6.1.yaml"
    install.parent.mkdir(parents=True, exist_ok=True)
    if not install.exists():
        urlretrieve("https://raw.githubusercontent.com/argoproj/argo-cd/v3.6.1/manifests/install.yaml", install)
    run(*KUBE, "apply", "-f", "-", input='apiVersion: v1\nkind: Namespace\nmetadata:\n  name: argocd\n')
    run(*KUBE, "apply", "--server-side", "-n", "argocd", "-f", str(install))
    existing = subprocess.run(["docker", "inspect", "ch6-git"], capture_output=True, text=True)
    if existing.returncode:
        run("docker", "build", "-t", "ch6-git-server:lab", "-f",
            str(Path(__file__).with_name("Dockerfile.git")), str(Path(__file__).parent))
        run("docker", "run", "-d", "--name", "ch6-git", "--restart=unless-stopped",
            "--network", "kind", "--mount",
            f"type=bind,source={remote},target=/git/income.git,readonly",
            "ch6-git-server:lab",
            "-c", "safe.directory=/git/income.git", "daemon", "--reuseaddr",
            "--base-path=/git", "--export-all", "--listen=0.0.0.0", "--verbose")
    else:
        run("docker", "start", "ch6-git")
    info = json.loads(subprocess.check_output(["docker", "inspect", "ch6-git"]))[0]
    ip = info["NetworkSettings"]["Networks"]["kind"]["IPAddress"]
    if not ip or not info["State"]["Running"]:
        raise RuntimeError("Local Git server is not running on the kind network")
    # Use the reachable Docker-network IP, not localhost inside a Kubernetes Pod.
    repo_url = f"git://{ip}/income.git"
    for resource in ("deployment/argocd-repo-server", "deployment/argocd-server",
                     "statefulset/argocd-application-controller"):
        run(*KUBE, "-n", "argocd", "rollout", "status", resource, "--timeout=180s")
    rendered = Path(__file__).with_name("application.yaml").read_text().replace("REPO_URL", repo_url)
    (CACHE / "argocd/application.yaml").write_text(rendered)
    run(*KUBE, "apply", "-f", "-", input=rendered)
    print(f"Argo CD source: {repo_url}")


if __name__ == "__main__":
    main()
