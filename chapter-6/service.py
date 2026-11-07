"""Step 4: serve the pipeline packaged with the Bento."""

from pathlib import Path
from datetime import datetime, timezone
import json
import os
import threading

import bentoml
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
    model_ref = bentoml.models.BentoModel(
        Path(__file__).with_name("model_tag.txt").read_text().strip()
    )

    def __init__(self):
        # BentoModel declares the model dependency for the build.
        self.model = bentoml.sklearn.load_model(self.model_ref)
        log_path = os.environ.get("CH6_REQUEST_LOG")
        self.request_log = Path(log_path) if log_path else None
        self.log_lock = threading.Lock()
        if self.request_log:
            self.request_log.parent.mkdir(parents=True, exist_ok=True)

    @bentoml.api
    def predict(self, features: IncomeFeatures) -> dict:
        row = pd.DataFrame([features.model_dump(by_alias=True)])
        prediction = int(self.model.predict(row)[0])
        # Optional local lab logging; only validated, successfully predicted inputs.
        if self.request_log:
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model_tag": str(self.model_ref.tag),
                "features": features.model_dump(by_alias=True),
                "prediction": prediction,
            }
            with self.log_lock, self.request_log.open("a") as stream:
                stream.write(json.dumps(record) + "\n")
        return {
            "prediction": prediction,
            "income_category": ">50K" if prediction == 1 else "<=50K",
        }
