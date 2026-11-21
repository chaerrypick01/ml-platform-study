"""Probe the local lab and emit evidence after Grafana returns both counter changes."""
import json
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROM = "http://127.0.0.1:18859"
GRAFANA = "http://127.0.0.1:18860"
API = "http://127.0.0.1:18857"


def fetch(url, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=body, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def counts(query):
    result = fetch(PROM + "/api/v1/query?" + urlencode({"query": query}))
    return {row["metric"]["outcome"]: int(float(row["value"][1]))
            for row in result["data"]["result"]}


def main():
    target, = fetch(PROM + "/api/v1/targets")["data"]["activeTargets"]
    assert target["health"] == "up", target["lastError"]
    dashboard = fetch(GRAFANA + "/api/dashboards/uid/movie-recommendations")["dashboard"]
    panel = dashboard["panels"][0]
    query = panel["targets"][0]["expr"]
    before = counts(query)
    assert set(before) == {"ok", "unknown_user"}
    start = int(time.time() * 1000) - 15000
    responses = []
    for user, expected in [(50, 200), (50, 200), (999999, 404)]:
        try:
            with urlopen(f"{API}/users/{user}/recommendations", timeout=10) as response:
                status = response.status
        except HTTPError as error:
            status = error.code
        assert status == expected, (user, status)
        responses.append({"user": user, "status": status})
    expected_counts = {"ok": before["ok"] + 2, "unknown_user": before["unknown_user"] + 1}
    for _ in range(15):
        time.sleep(1)
        after = counts(query)
        if after == expected_counts:
            break
    else:
        raise RuntimeError(f"No matching scrape: {before} -> {after}")
    time.sleep(6)  # Allow a full Grafana range-query step after the new scrape.
    end = int(time.time() * 1000)
    result = fetch(GRAFANA + "/api/ds/query", {
        "from": str(start), "to": str(end),
        "queries": [{**panel["targets"][0], "datasource": panel["datasource"],
                     "intervalMs": 1000, "maxDataPoints": 100}],
    })["results"]["A"]
    series = {}
    for frame in result["frames"]:
        outcome = frame["schema"]["fields"][1]["labels"]["outcome"]
        timestamps, values = frame["data"]["values"]
        series[outcome] = list(zip(timestamps, values))
    for key in before:
        values = [value for _, value in series[key]]
        assert before[key] in values and values[-1] == after[key], (key, values)
    print(json.dumps({"scrape_url": target["scrapeUrl"], "health": target["health"],
                      "responses": responses, "before": before, "after": after,
                      "dashboard": dashboard["uid"], "panel_query": query,
                      "grafana_samples_epoch_ms": series}, indent=2))


if __name__ == "__main__":
    main()
