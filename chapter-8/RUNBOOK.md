# Chapter 8 — YOLO 학습·검증 실습

모든 명령은 저장소 루트에서 실행한다. Python 3.11을 사용하며 이 장의 `.venv`에만 의존성을 설치한다. 기존 가상환경이 있으면 재사용한다.

KFP 실습은 공용 로컬 클러스터 `ch5-lab`, `chapter-5/.kube/config`, 레지스트리 `localhost:5002`를 사용한다. 최초 인프라 구성은 [5장](../chapter-5/README.md)과 [6장](../chapter-6/RUNBOOK.md)을 참고한다. 각 장의 Python 환경과 컨테이너 이미지는 별개다. 이미 KFP UI에 연결돼 있으면 다음 port-forward는 생략한다.

```bash
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab -n kubeflow port-forward --address 127.0.0.1 svc/ml-pipeline-ui 8080:80
```

## 환경 준비

```bash
python3.11 -m venv chapter-8/.venv
chapter-8/.venv/bin/python -m pip install -r chapter-8/requirements.txt
chapter-8/.venv/bin/python -m pip check
```

이 장은 YOLO·PyTorch, 학습 로그용 TensorBoard·MLflow, KFP SDK를 설치한다. 7장의 가상환경을 사용하지 않는다.

## 1. 입력 데이터와 가중치

7장에서 만든 데이터셋을 `--dataset`으로 받는다. 8장만 시작한다면 이 장의 Python으로 재사용 데이터 준비 코드를 실행할 수 있다. 결과는 8장 안에 저장한다.

```bash
chapter-8/.venv/bin/python chapter-8/prepare_data.py --output chapter-8/outputs/coco128
```

```bash
mkdir -p chapter-8/.cache
curl -fL https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt -o chapter-8/.cache/yolov8n.pt
```

## 2. 로컬 학습과 검증

```bash
chapter-8/.venv/bin/python chapter-8/train.py train --dataset chapter-8/outputs/coco128 --weights chapter-8/.cache/yolov8n.pt --output chapter-8/outputs/train-new --epochs 1 --device cpu
```

체크포인트 비교는 MLflow `127.0.0.1:5001`을 사용한다. [4장 실행 안내](../chapter-4/Readme.md)에 따라 서버를 시작하고 다음 명령을 실행한다. 기존 서버는 재사용한다.

```bash
OMP_NUM_THREADS=4 chapter-8/.venv/bin/python chapter-8/experiments.py --dataset chapter-8/outputs/coco128 --weights chapter-8/.cache/yolov8n.pt --output chapter-8/outputs/experiment-new
OMP_NUM_THREADS=4 chapter-8/.venv/bin/python chapter-8/benchmark.py --dataset chapter-8/outputs/coco128 --weights chapter-8/.cache/yolov8n.pt --output chapter-8/outputs/benchmark-new
```

`experiments.py`에도 CPU/MPS 측정이 포함된다. 시간 측정만 반복할 때 `benchmark.py`를 사용한다. 각 명령의 출력 디렉터리는 새 이름으로 지정한다.

## 3. 학습·검증 파이프라인

```bash
docker build --platform linux/arm64 -t localhost:5002/ch8-lab:v1 -f chapter-8/Dockerfile .
docker push localhost:5002/ch8-lab:v1
```

컴파일 전에 `LAB_IMAGE`를 해당 이미지 digest로 지정하면 실행 이미지를 고정할 수 있다. 기본값은 위 `v1` 태그다.

```bash
chapter-8/.venv/bin/python chapter-8/pipeline.py
chapter-8/.venv/bin/python chapter-8/submit.py artifacts --output chapter-8/outputs/artifacts-run.json
chapter-8/.venv/bin/python chapter-8/verify_runs.py
```

실험 이름은 `chapter-8`이다. 준비 → 학습 → 검증 단계가 실행되며 이미지 빌드 시 7장의 데이터 준비 소스를 포함한다. 7장 실습을 먼저 실행할 필요는 없다. 입력·가중치·Run 기록은 이 장의 `outputs/`에 저장한다.

## 결과

[실습 결과](RESULTS.md)를 참고한다. MPS는 Mac 호스트에서 사용하며 kind Pod는 CPU로 실행한다.
