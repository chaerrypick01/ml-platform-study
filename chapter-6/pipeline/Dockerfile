FROM python:3.10-slim
ENV DO_NOT_TRACK=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-drift.txt .
RUN pip install --no-cache-dir -r requirements-drift.txt
COPY gate.py report_drift.py ./
COPY data/ ./data/
ENTRYPOINT ["python", "/app/gate.py"]
