FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 MPLBACKEND=Agg YOLO_AUTOINSTALL=false PYTHONPATH=/lab OMP_NUM_THREADS=2
WORKDIR /lab
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY chapter-8/requirements.txt /lab/requirements.txt
RUN pip install --timeout 120 --retries 5 --no-cache-dir -r requirements.txt
COPY chapter-7/lab_data.py chapter-7/coco_names.yaml chapter-8/train.py /lab/
COPY chapter-8/.cache/yolov8n.pt /lab/yolov8n.pt
