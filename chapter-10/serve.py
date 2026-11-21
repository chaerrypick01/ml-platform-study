"""Serve the local Chapter 9 MovieLens checkpoint with one worker."""
from collections import Counter
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from recommender import Recommender

artifacts = Path(__file__).resolve().parents[1] / "chapter-9/outputs/movie-local"
recommender = Recommender(artifacts)
counts = Counter()
app = FastAPI()


@app.get("/users/{user_id}/recommendations")
async def recommend(user_id: int):
    if user_id not in recommender.model["users"]:
        counts["unknown_user"] += 1
        raise HTTPException(404, "unknown_user")
    result = recommender.recommend(user_id)
    counts["ok"] += 1
    return result


@app.get("/metrics")
async def metrics():
    lines = ["# TYPE recommendation_requests_total counter"]
    for outcome in ("ok", "unknown_user"):
        lines.append(f'recommendation_requests_total{{outcome="{outcome}"}} {counts[outcome]}')
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
