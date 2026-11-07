"""Publish only the lab manifest to a separate, local Git remote."""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "chapter-6/.cache/gitops"
WORK = CACHE / "work"
REMOTE = CACHE / "remote.git"
MANIFEST = Path(__file__).with_name("income-service.yaml")


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message", default="Update income serving configuration")
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    if not REMOTE.exists():
        run("git", "init", "--bare", "--initial-branch=main", str(REMOTE))
        hook = REMOTE / "hooks/post-update"
        hook.write_text("#!/bin/sh\nexec git update-server-info\n")
        hook.chmod(0o755)
    if not (WORK / ".git").exists():
        run("git", "init", "--initial-branch=main", str(WORK))
        run("git", "remote", "add", "origin", str(REMOTE), cwd=WORK)
        # Dedicated local learning repository; main project history is untouched.
        for key in ("user.name", "user.email"):
            value = subprocess.check_output(["git", "config", key], cwd=ROOT, text=True).strip()
            run("git", "config", key, value, cwd=WORK)
    (WORK / "income-service.yaml").write_text(MANIFEST.read_text())
    run("git", "add", "income-service.yaml", cwd=WORK)
    changed = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=WORK)
    if changed.returncode == 1:
        run("git", "commit", "-m", args.message, cwd=WORK)
    elif changed.returncode != 0:
        changed.check_returncode()
    run("git", "push", "origin", "main", cwd=WORK)
    run("git", "--git-dir", str(REMOTE), "update-server-info")
    run("git", "log", "-1", "--oneline", cwd=WORK)


if __name__ == "__main__":
    main()
