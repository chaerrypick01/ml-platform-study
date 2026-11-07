"""Send current then shifted input through a running prediction API."""

import argparse
from pathlib import Path

import pandas as pd
import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:3003/predict")
    args = parser.parse_args()
    folder = Path(__file__).parent / "outputs/drift"
    with requests.Session() as session:
        for name in ("current", "shifted"):
            records = pd.read_csv(folder / f"{name}.csv").to_dict(orient="records")
            for index, features in enumerate(records, start=1):
                response = session.post(args.endpoint, json={"features": features}, timeout=30)
                response.raise_for_status()
                result = response.json()
                if result["prediction"] not in (0, 1):
                    raise ValueError(f"Unexpected prediction: {result}")
                if index % 250 == 0:
                    print(f"{name}: {index}/{len(records)} successful requests", flush=True)


if __name__ == "__main__":
    main()
