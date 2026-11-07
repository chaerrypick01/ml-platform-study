"""Verify actual container predictions and validation before publishing an image."""
import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def check(endpoint, sample):
    second = {"features": {"Workclass": "Private", "Education": "Masters",
        "Marital-Status": "Married-civ-spouse", "Occupation": "Exec-managerial",
        "Relationship": "Husband", "Race": "White", "Sex": "Male",
        "Native_country": "United-States"}}
    for payload, expected in [(sample, 0), (second, 1), ({"features": {"Education": "Masters"}}, None)]:
        request = Request(endpoint + "/predict", data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=30) as response:
                result = json.load(response)
                assert expected is not None and result["prediction"] == expected, result
                assert result["income_category"] == (">50K" if expected else "<=50K")
        except HTTPError as error:
            assert expected is None and error.code == 400, error
    print("PASS: predictions 0/1 and invalid-input HTTP 400")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--sample", type=Path, default=Path("sample_request.json"))
    args = parser.parse_args()
    check(args.endpoint, json.loads(args.sample.read_text()))
