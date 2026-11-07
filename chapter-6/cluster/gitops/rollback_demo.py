"""Commit the previous tested image to Git, verify rollback, then restore current."""
import json
from pathlib import Path
import subprocess
import sys

from verify_deployment import CHAPTER, verify


if __name__ == "__main__":
    record = json.loads((CHAPTER / ".cache/ci/latest.json").read_text())
    assert record["status"] == "SUCCEEDED", "Need a successful CI image first"
    assert record["image"] != record["previous_image"], "Need two different image digests"
    manifest = Path(__file__).with_name("income-service.yaml")
    assert manifest.read_text() == record["manifest"], "Deployment source changed; review before rollback"
    evidence = []
    for state, content in (("rollback", record["previous_manifest"]), ("restore", record["manifest"])):
        manifest.write_text(content)
        subprocess.run([sys.executable, str(Path(__file__).with_name("publish.py")),
                        "--message", f"{state.title()} tested serving image for rollback exercise"], check=True)
        result = verify()
        evidence.append({"action": state, **result})
    out = CHAPTER / "outputs/rollback-verification.json"
    out.write_text(json.dumps(evidence, indent=2))
    print(f"Verified rollback and restore through Git: {out}")
