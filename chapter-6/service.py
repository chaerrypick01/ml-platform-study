"""Step 4: serve the pipeline packaged with the Bento."""

from pathlib import Path
from datetime import datetime, timezone
import os

import bentoml
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from request_log import RequestLog


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
    model_ref = bentoml.models.BentoModel(
        Path(__file__).with_name("model_tag.txt").read_text().strip()
    )

    def __init__(self):
        # BentoModel declares the model dependency for the build.
        self.model = bentoml.sklearn.load_model(self.model_ref)
        self.model_uri = bentoml.sklearn.get(self.model_ref.tag).info.metadata.get("mlflow_model_uri")
        log_path = os.environ.get("CH6_REQUEST_LOG")
        stdout = os.environ.get("CH6_LOG_STDOUT") == "1"
        self.request_log = RequestLog(log_path, stdout) if log_path or stdout else None

    @bentoml.api
    def predict(self, features: IncomeFeatures) -> dict:
        row = pd.DataFrame([features.model_dump(by_alias=True)])
        prediction = int(self.model.predict(row)[0])
        # Optional local lab logging; only validated, successfully predicted inputs.
        if self.request_log:
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model_tag": str(self.model_ref.tag),
                "model_uri": self.model_uri,
                "release": os.environ.get("CH6_RELEASE", "local"),
                "features": features.model_dump(by_alias=True),
                "prediction": prediction,
            }
            self.request_log.submit(record)
        return {
            "prediction": prediction,
            "income_category": ">50K" if prediction == 1 else "<=50K",
        }
