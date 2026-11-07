"""Snapshot serving sources into a local Git remote; its push hook runs CI."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys

HERE = Path(__file__).resolve().parent
CHAPTER = HERE.parent
CACHE = CHAPTER / ".cache/ci"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message", default="Build monitored income service")
    parser.add_argument("--retry", action="store_true", help="Rerun CI for the current pushed commit")
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    remote, work = CACHE / "source.git", CACHE / "work"
    if not remote.exists():
        run("git", "init", "--bare", "--initial-branch=main", str(remote))
    hook = remote / "hooks/post-receive"
    hook.write_text("#!/bin/sh\nexec " + shlex.join([sys.executable, str(HERE / "run.py")]) + "\n")
    hook.chmod(0o755)
    if not (work / ".git").exists():
        run("git", "init", "--initial-branch=main", str(work))
        run("git", "remote", "add", "origin", str(remote), cwd=work)
        for key in ("user.name", "user.email"):
            value = subprocess.check_output(["git", "config", key], cwd=CHAPTER, text=True).strip()
            run("git", "config", key, value, cwd=work)
    sources = [CHAPTER / name for name in ("service.py", "request_log.py", "bentofile.yaml",
               "model_tag.txt", "sample_request.json", "requirements-serving.lock.txt")]
    sources += [HERE / "test_service.py", HERE / "smoke.py"]
    for source in sources:
        (work / source.name).write_bytes(source.read_bytes())
    run("git", "add", "--", *[p.name for p in sources], cwd=work)
    difference = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=work)
    if difference.returncode == 1:
        run("git", "commit", "-m", args.message, cwd=work)
    elif difference.returncode != 0:
        difference.check_returncode()
    previous = subprocess.run(["git", "--git-dir", str(remote), "rev-parse", "--verify", "main"],
                              text=True, capture_output=True).stdout.strip()
    run("git", "push", "origin", "main", cwd=work)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=work, text=True).strip()
    if args.retry and previous == revision:
        run(sys.executable, str(HERE / "run.py"), input=f"{'0' * 40} {revision} refs/heads/main\n")
    latest = CACHE / "latest.json"
    if not latest.exists():
        raise RuntimeError("No CI result was recorded")
    result = json.loads(latest.read_text())
    if result["source_revision"] != revision or result["status"] != "SUCCEEDED":
        raise RuntimeError(f"CI did not succeed; inspect {latest} and jobs/*/job.log")
    print(f"CI records: {CACHE / 'jobs'} (push acceptance alone does not mean CI success)")


if __name__ == "__main__":
    main()
