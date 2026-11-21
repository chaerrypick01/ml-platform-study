"""Serve the local Chapter 9 MovieLens checkpoint with one worker."""
import hashlib
import json
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import torch
from fastapi import FastAPI, HTTPException, Response

artifacts = Path(__file__).resolve().parents[1] / "chapter-9/outputs/movie-local"
archive = artifacts / "movielens.zip"
metadata = json.loads((artifacts / "result.json").read_text())
if hashlib.sha256(archive.read_bytes()).hexdigest() != metadata["archive_sha256"]:
    raise ValueError("MovieLens archive differs from training input")

model = torch.load(artifacts / "model.pt", map_location="cpu", weights_only=False)
weights = model["state_dict"]
with ZipFile(archive) as data:
    ratings = pd.read_csv(data.open("ml-latest-small/ratings.csv"))
    titles = pd.read_csv(data.open("ml-latest-small/movies.csv")).set_index("movieId").title
training = ratings.sample(n=metadata["sample_size"], random_state=42).iloc[:metadata["train_rows"]]
seen = training.groupby("userId").movieId.agg(set)
counts = Counter()
app = FastAPI()


@app.get("/users/{user_id}/recommendations")
async def recommend(user_id: int):
    if user_id not in model["users"]:
        counts["unknown_user"] += 1
        raise HTTPException(404, "unknown_user")
    u = model["users"][user_id]
    scores = (model["mean"] + (weights["user.weight"][u] * weights["movie.weight"]).sum(1)
              + weights["ub.weight"][u] + weights["mb.weight"][:, 0])
    candidates = [m for m in model["movies"] if m not in seen[user_id]]
    ranked = sorted(candidates, key=lambda m: (-scores[model["movies"][m]].item(), m))
    items = [{"movie_id": int(m), "title": titles[m],
              "predicted_rating": round(scores[model["movies"][m]].item(), 3)} for m in ranked[:3]]
    counts["ok"] += 1
    return {"user_id": user_id, "recommendations": items}


@app.get("/metrics")
async def metrics():
    lines = ["# TYPE recommendation_requests_total counter"]
    for outcome in ("ok", "unknown_user"):
        lines.append(f'recommendation_requests_total{{outcome="{outcome}"}} {counts[outcome]}')
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
