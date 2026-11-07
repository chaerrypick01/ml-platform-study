"""Step 3: serve the existing income pipeline through HTTP."""

import os

import bentoml
import mlflow
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


class IncomeFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    Workclass: str
    Education: str
    marital_status: str = Field(alias="Marital-Status")
    Occupation: str
    Relationship: str
    Race: str
    Sex: str
    Native_country: str


@bentoml.service(workers=1)
class IncomeService:
    def __init__(self):
        # Load once when the service worker starts, not on every request.
        mlflow.set_tracking_uri(
            os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001")
        )
        self.model = mlflow.sklearn.load_model(
            "models:/m-ca51f8c9ef8541adba6bcfe3eefceee7"
        )

    @bentoml.api
    def predict(self, features: IncomeFeatures) -> dict:
        row = pd.DataFrame([features.model_dump(by_alias=True)])
        prediction = int(self.model.predict(row)[0])
        return {
            "prediction": prediction,
            "income_category": ">50K" if prediction == 1 else "<=50K",
        }
