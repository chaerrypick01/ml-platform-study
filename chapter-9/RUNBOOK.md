# Chapter 9 — PVC·학습 추적 실습

모든 명령은 저장소 루트에서 실행한다. Python 3.11을 사용하며 이 장의 `.venv`에만 의존성을 설치한다. 기존 가상환경이 있으면 재사용한다.

KFP 실습은 공용 로컬 클러스터 `ch5-lab`, `chapter-5/.kube/config`, 레지스트리 `localhost:5002`를 사용한다. 최초 인프라 구성은 [5장](../chapter-5/README.md)과 [6장](../chapter-6/RUNBOOK.md)을 참고한다. 각 장의 Python 환경과 컨테이너 이미지는 별개다. 이미 KFP UI에 연결돼 있으면 다음 port-forward는 생략한다.

```bash
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab -n kubeflow port-forward --address 127.0.0.1 svc/ml-pipeline-ui 8080:80
```

## 환경 준비

```bash
python3.11 -m venv chapter-9/.venv
chapter-9/.venv/bin/python -m pip install -r chapter-9/requirements.txt
chapter-9/.venv/bin/python -m pip check
```

이 장의 의존성은 PVC용 KFP Kubernetes 확장, TensorBoard·MLflow, 영화 평점용 pandas·PyTorch와 PVC 학습 부하용 YOLO다. 8장과 겹치는 라이브러리가 있지만 설치 환경은 분리한다.

## 1. 전용 이미지 준비

```bash
mkdir -p chapter-9/.cache
curl -fL https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt -o chapter-9/.cache/yolov8n.pt
```

```bash
docker build --platform linux/arm64 -t localhost:5002/ch9-lab:v1 -f chapter-9/Dockerfile .
docker push localhost:5002/ch9-lab:v1
```

컴파일 전에 `LAB_IMAGE`를 해당 이미지 digest로 지정하면 실행 이미지를 고정할 수 있다. 기본값은 위 `v1` 태그다.

Dockerfile은 7장의 데이터 준비 함수와 8장의 학습 함수를 소스로 재사용한다. 8장의 `.venv`·가중치 캐시·실행 결과는 사용하지 않는다. 이 장의 가중치는 `chapter-9/.cache/`에 둔다.

## 2. PVC 생명주기

```bash
chapter-9/.venv/bin/python chapter-9/pvc_lifecycle.py
chapter-9/.venv/bin/python chapter-9/verify_followups.py
```

실행마다 고유한 64Mi PVC를 만들고 쓰기·읽기·해시 대조·삭제 요청을 실행한다. 기록은 `chapter-9/outputs/pvc-lifecycle/`에 저장한다. 재제출 시 최신 기록이 갱신된다. API 호출 컴포넌트에는 PVC 생성·삭제 권한이 필요하다.

삭제 요청 후 PVC가 `Terminating`이면 해당 볼륨을 참조하는 완료 Pod의 로그를 보존한 뒤 그 Pod만 정리한다. PVC와 PV가 실제 사라졌는지 확인한다. [오류 해결과 삭제 지연 기록](RESULTS.md)을 참고한다.

## 3. PVC 학습·TensorBoard·MLflow

MLflow 서버 `127.0.0.1:5001`을 재사용한다. Pod의 접속 주소는 `host.docker.internal:5001`이다.

```bash
chapter-9/.venv/bin/python chapter-9/pipelines.py
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab apply -f chapter-9/cluster.yaml
chapter-9/.venv/bin/python chapter-9/submit.py pvc --output chapter-9/outputs/pvc-run.json
chapter-9/.venv/bin/python chapter-9/verify_runs.py --records chapter-9/outputs/pvc-run.json
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab -n kubeflow port-forward --address 127.0.0.1 svc/chapter9-tensorboard 6006:6006
```

TensorBoard는 http://127.0.0.1:6006, MLflow는 http://127.0.0.1:5001 에서 확인한다. 실험은 KFP의 `chapter-9`, MLflow의 `chapter-8-9-yolo`에 기록된다. 학습 함수의 MLflow 이름은 기존 실행과 연속성을 위해 유지한다.

## 4. 영화 평점 예측 — 확장 실습

```bash
chapter-9/.venv/bin/python chapter-9/recommend.py --output chapter-9/outputs/movie-new
chapter-9/.venv/bin/python chapter-9/submit.py movie --output chapter-9/outputs/movie-run.json
chapter-9/.venv/bin/python chapter-9/verify_runs.py
```

첫 명령은 호스트 실행이며 두 번째는 별도의 KFP 실행이다. 기본 검증은 PVC·영화 Run을 모두 확인한다. 9.2·9.3은 스터디 다음 주차 범위의 확장 실습이다.

## 정리

port-forward는 해당 터미널에서 종료한다. 필요한 모델·로그를 보관한 뒤 이번 장의 학습 리소스만 정리한다.

```bash
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab delete -f chapter-9/cluster.yaml
```
