# Chapter 7 — 데이터 준비 실습

모든 명령은 저장소 루트에서 실행한다. Python 3.11을 사용하며 이 장의 `.venv`에만 의존성을 설치한다. 기존 가상환경이 있으면 재사용한다.

KFP 실습은 공용 로컬 클러스터 `ch5-lab`, `chapter-5/.kube/config`, 레지스트리 `localhost:5002`를 사용한다. 최초 인프라 구성은 [5장](../chapter-5/README.md)과 [6장](../chapter-6/RUNBOOK.md)을 참고한다. 각 장의 Python 환경과 컨테이너 이미지는 별개다. 이미 KFP UI에 연결돼 있으면 다음 port-forward는 생략한다.

```bash
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab -n kubeflow port-forward --address 127.0.0.1 svc/ml-pipeline-ui 8080:80
```

## 환경 준비

```bash
python3.11 -m venv chapter-7/.venv
chapter-7/.venv/bin/python -m pip install -r chapter-7/requirements.txt
chapter-7/.venv/bin/python -m pip check
```

PyYAML은 COCO 설정을 읽고, pandas·pyarrow는 MovieLens를 Parquet로 변환한다. KFP SDK는 파이프라인 컴파일·제출에 사용한다. 이 장에는 torch·YOLO·MLflow가 필요하지 않다.

## 1. COCO128 다운로드·검사·분할

```bash
chapter-7/.venv/bin/python chapter-7/lab_data.py --output chapter-7/outputs/coco128-new
```

출력은 빈 디렉터리여야 한다. `data.yaml`, `manifest.json`, 이미지·라벨을 생성한다. 이 디렉터리를 8장 `--dataset`에 전달할 수 있다.

## 2. MovieLens 준비·QA를 KFP에서 실행

```bash
docker build --platform linux/arm64 -t localhost:5002/ch7-data:v1 -f chapter-7/Dockerfile .
docker push localhost:5002/ch7-data:v1
```

컴파일 전에 `LAB_IMAGE`를 해당 이미지 digest로 지정하면 실행 이미지를 고정할 수 있다. 기본값은 위 `v1` 태그다.

```bash
chapter-7/.venv/bin/python chapter-7/movie_data_pipeline.py --submit
chapter-7/.venv/bin/python chapter-7/verify_run.py
```

실험 이름은 `chapter-7`이다. 실행 기록과 로그는 `chapter-7/outputs/movie-data/`에 저장한다. 검증 명령은 준비·QA 작업이 모두 성공해야 종료 코드 0을 반환한다. 재제출하면 최신 Run 기록을 갱신한다.

## 결과

[실습 결과](RESULTS.md)를 참고한다. 이 장의 실행은 8·9장의 가상환경이나 이미지에 의존하지 않는다.
