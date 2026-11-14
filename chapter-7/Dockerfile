FROM python:3.11-slim
WORKDIR /lab
COPY chapter-7/requirements.txt /lab/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY chapter-7/lab_data.py chapter-7/coco_names.yaml /lab/
