from importlib.metadata import version
from pathlib import Path
import sys

import mlflow.pyfunc
from mlflow.models import ModelSignature
from mlflow.types import ColSpec, Schema

from recommender import Recommender


class MovieRecommendations(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        self.engine = Recommender(Path(context.artifacts["model.pt"]).parent)

    def predict(self, context, model_input):
        return [self.engine.recommend(int(user)) for user in model_input["user_id"]]


if __name__ == "__main__":
    chapter = Path(__file__).resolve().parent
    artifacts = chapter.parent / "chapter-9/outputs/movie-local"
    mlflow.pyfunc.save_model(
        path=sys.argv[1],
        python_model=MovieRecommendations(),
        artifacts={name: str(artifacts / name) for name in ("model.pt", "result.json", "movielens.zip")},
        code_paths=[str(chapter / "recommender.py")],
        signature=ModelSignature(inputs=Schema([ColSpec("long", "user_id")])),
        pip_requirements=[f"{name}=={version(name)}" for name in ("mlflow", "pandas", "torch", "cloudpickle")],
    )
