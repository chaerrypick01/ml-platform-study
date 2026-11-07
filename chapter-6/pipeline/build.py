"""Build a separate Evidently image with versioned lab reference data."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

CHAPTER = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    folder = CHAPTER / ".cache/gate-build" / version
    (folder / "data").mkdir(parents=True)
    for name in ("reference.csv", "current.csv", "shifted.csv", "manifest.json"):
        shutil.copy2(CHAPTER / "outputs/drift" / name, folder / "data" / name)
    shutil.copy2(CHAPTER / "model_tag.txt", folder / "data/model_tag.txt")
    for source in (CHAPTER / "requirements-drift.txt", CHAPTER / "report_drift.py",
                   Path(__file__).with_name("gate.py"), Path(__file__).with_name("Dockerfile")):
        shutil.copy2(source, folder / source.name)
    image = f"localhost:5002/ch6-drift-gate:{version}"
    subprocess.run(["docker", "build", "--platform", "linux/arm64", "-t", image, str(folder)], check=True)
    model_tag = (CHAPTER / "model_tag.txt").read_text().strip()
    for batch, expected in (("current", "True"), ("shifted", "False")):
        output = subprocess.check_output(["docker", "run", "--rm", image, "gate", "--batch", batch,
            "--model-tag", model_tag, "--allow", "/tmp/allow", "--output", "/tmp/report.json"], text=True)
        assert f"allow_inference={expected}" in output, output
        print(output, flush=True)
    subprocess.run(["docker", "push", image], check=True)
    info = json.loads(subprocess.check_output(["docker", "image", "inspect", image]))[0]
    pinned = next(x for x in info["RepoDigests"] if x.startswith("localhost:5002/ch6-drift-gate@"))
    (CHAPTER / ".cache/gate-image.txt").write_text(pinned + "\n")
    print(pinned)
