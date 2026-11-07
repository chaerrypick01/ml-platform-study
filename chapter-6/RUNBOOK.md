# Chapter 6 — 단계별 재실행 명령

구조와 검증 범위는 [README](README.md)를 먼저 읽는다. 아래 명령은 초기 실습부터 최종 환경까지의 단계별 기록이다.
이미 GitOps를 연결했다면 초기 단계 YAML을 다시 적용하지 말고 필요한 단계만 선택한다.

4장의 학습된 Pipeline(OneHotEncoder + RandomForest)을 HTTP API로 제공한다.
요청에 피처 8개를 직접 넣는다. Feast 조회는 아직 연결하지 않았다.
드리프트 실습은 오프라인 비교, 로컬 API 요청 로그, Kubernetes 요청 로그 비교를 포함한다.
후반부에서는 로컬 Git hook CI, Argo CD 배포, KFP 조건부 추론과 이미지 롤백을 연결한다.

## 파일

- `service_mlflow.py`: 서버 시작 시 MLflow에서 모델을 가져오는 첫 실습
- `import_model.py`: MLflow 모델을 BentoML 모델 저장소에 복사하고 정확한 버전을 `model_tag.txt`에 기록
- `service.py`: BentoML에 저장된 모델을 사용하는 서비스
- `bentofile.yaml`: 패키지에 포함할 파일과 Python 의존성 정의
- `sample_request.json`: 첫 번째 예측 요청
- `inspect_memory.py`: 별도 프로세스에서 모델 파일 크기와 로딩 전후 RSS 측정

<a id="serving"></a>

## 환경 준비

저장소 루트에서 실행한다.

```bash
uv venv --python chapter-4/venv/bin/python chapter-6/.venv
uv pip install --python chapter-6/.venv/bin/python -r chapter-6/requirements.txt
chapter-6/.venv/bin/python chapter-6/import_model.py
```

모델을 가져올 때만 MLflow(`127.0.0.1:5001`)와 그 아티팩트 저장소가 필요하다.
새로 가져오면 모델 버전이 바뀌므로 Bento도 다시 빌드한다.

## Bento 빌드와 컨테이너 실행

현재 실습 머신의 Apple Silicon에 맞춘 Linux ARM64 빌드다.
`requirements-serving.lock.txt`는 Python 3.10 및 Linux ARM64를 대상으로 고정한 서빙 의존성이다.
의존성을 바꾸면 저장소 루트에서 다음 명령으로 다시 생성한다.

```bash
uv pip compile chapter-6/requirements-serving.in --python-version 3.10 \
  --python-platform aarch64-manylinux_2_36 -o chapter-6/requirements-serving.lock.txt
```

아래 명령은 `chapter-6`에서 실행한다. 이미 만든 버전을 다시 빌드하려면 새 버전명을 사용한다.

```bash
cd chapter-6
BENTOML_DO_NOT_TRACK=True .venv/bin/bentoml build \
  --platform aarch64-manylinux_2_36 --version container-lab-v2
BENTOML_DO_NOT_TRACK=True .venv/bin/bentoml containerize \
  income_service:container-lab-v2 -t ch6-income:lab-v2 \
  --opt platform=linux/arm64 --opt progress=plain
docker run -d --name ch6-income-lab \
  -p 127.0.0.1:3002:3000 \
  -e BENTOML_DO_NOT_TRACK=True \
  ch6-income:lab-v2 serve
```

호스트의 가상환경이나 모델 디렉터리를 마운트하지 않는다.
이미지에 들어간 코드·모델·Python 패키지로 서버가 실행된다.
3002는 호스트 포트, 3000은 컨테이너 내부 서버 포트다.

```bash
curl -sS http://127.0.0.1:3002/predict \
  -H 'Content-Type: application/json' \
  --data-binary @sample_request.json
echo
docker logs --tail 30 ch6-income-lab
docker stats --no-stream ch6-income-lab
```

첫 요청의 기대 응답은 `{"prediction": 0, "income_category": "<=50K"}`다.
이미지 크기는 디스크 사용량이며 실행 중 RAM 사용량과 다르다.

```bash
docker stop ch6-income-lab
docker start ch6-income-lab
```

외부 레지스트리 push와 Kubernetes 배포는 이 단계에서 수행하지 않는다.

## 드리프트 비교 보고서

서빙과 별도 환경에서 Evidently 0.7.23을 실행한다. 저장소 루트에서:

```bash
uv venv --python chapter-4/venv/bin/python chapter-6/.venv-drift
uv pip install --python chapter-6/.venv-drift/bin/python -r chapter-6/requirements-drift.txt
chapter-6/.venv/bin/python chapter-6/prepare_drift_data.py
chapter-6/.venv-drift/bin/python chapter-6/report_drift.py
open chapter-6/outputs/drift/current_report.html
open chapter-6/outputs/drift/shifted_report.html
```

`prepare_drift_data.py`는 기존 학습 데이터 해시와 행 분할 기록을 사용한다.
최종 학습(train + validation)에서 기준 1,000행, test에서 현재 1,000행을 뽑는다.
변형 데이터는 현재 데이터의 80% 행에서 Education을 Masters로 변경한 것이다.
실제 운영 요청을 수집한 데이터가 아니며 정답 열도 제외한다.

모든 피처를 범주형으로 명시하고 Jensen–Shannon 거리 0.1을 피처별 임계값으로 사용한다.
데이터셋 전체 판정은 드리프트된 피처 비율 0.5를 기준으로 한다.
현재 표본에서는 Native_country가, 변형 표본에서는 Native_country와 Education이 임계값을 넘는다.
이는 모델 정확도 하락을 증명하지 않는다. 표본 차이와 운영상 중요한 변화를 구분해 해석해야 한다.
보고서의 피처별 경고와 데이터셋 전체 판정은 서로 다른 기준이다.

참고: [Evidently 드리프트 설정](https://docs.evidentlyai.com/metrics/customize_data_drift)

## API 요청으로 드리프트 검사

`CH6_REQUEST_LOG`를 설정하면 `service.py`는 검증과 예측에 성공한 입력의 피처,
예측값, 모델 버전, 시간을 JSONL로 기록한다. 요청마다 모델을 다시 읽지 않는다.
별도 `monitor_requests.py`가 로그를 읽어 겹치지 않는 1,000건 단위 보고서를 만든다.
슬라이딩 윈도나 요청마다 보고서를 만드는 방식은 아니다.

저장소 루트에서 터미널 3개로 실행한다. 반복 실습 시 `live-demo`를 새 디렉터리명으로
바꾸고 모든 터미널에서 같은 이름을 사용한다. 모니터는 시작부터 로그를 읽으며,
기존 보고서를 덮어쓰지 않는다. 3003 포트가 사용 중이면 기존 실습 서버를 종료하거나
다른 포트를 정하고 송신 스크립트의 `--endpoint`도 맞춘다.

```bash
# 터미널 1: 로그 기록을 켠 서버 (chapter-6에서 실행)
cd chapter-6
CH6_REQUEST_LOG="$(pwd)/outputs/live-demo/requests.jsonl" \
  BENTOML_DO_NOT_TRACK=True .venv/bin/bentoml serve service:IncomeService \
  --host 127.0.0.1 --port 3003
```

```bash
# 터미널 2: 별도 모니터; 2개 윈도 처리 후 종료 (저장소 루트)
chapter-6/.venv-drift/bin/python chapter-6/monitor_requests.py \
  --request-log chapter-6/outputs/live-demo/requests.jsonl
```

```bash
# 터미널 3: current 1,000건 → shifted 1,000건 (서버 초기화 완료 후)
chapter-6/.venv/bin/python chapter-6/send_drift_requests.py
```

`window_001.html`은 첫 1,000건, `window_002.html`은 다음 1,000건의 보고서다.
실습은 순차 전송·단일 워커·로컬 파일 기준이다. 기본 300초 안에 2개 윈도를 채우지
못하면 모니터가 오류로 종료한다. 자동 재학습이나 외부 알림 전송은 연결하지 않았다.
3002 포트 컨테이너는 이전 이미지이므로 이 기록 기능을 쓰려면 새 버전으로 빌드해야 한다.

## 피처별 드리프트 경고

모니터는 각 윈도에서 Evidently 피처 검사가 `FAIL`인 항목을 콘솔 및 `alerts.jsonl`에
기록한다. 데이터셋 전체 판정과 별개이며, 정확도 하락이나 재학습 필요성을 단정하지 않는다.
액션 `review_data_change`는 입력 수집·전처리 변경과 사용자 구성 변화 등을 검토하라는 의미다.
이는 로컬 실습용 경고 기록이며 Slack·메일 등의 외부 전송은 수행하지 않는다.

이미 생성한 보고서에서도 경고 파일을 만들 수 있다. 같은 디렉터리로 재실행하면 경고를
추가 중복 기록하지 않고 해당 보고서들 기준으로 파일을 다시 생성한다.

```bash
chapter-6/.venv-drift/bin/python chapter-6/drift_alerts.py \
  chapter-6/outputs/live-20261108T032403
```

이 실습에서는 첫 윈도에 Native_country, 두 번째 윈도에 Education과 Native_country
경고가 생긴다. 같은 피처가 여러 윈도에서 감지되면 윈도마다 기록하며, 알림 빈도 제한이나
연속 감지 조건은 아직 적용하지 않는다.

<a id="kserve"></a>

## KServe로 기존 Bento 이미지 배포

기존 로컬 kind 클러스터 `ch5-lab`(Kubernetes 1.31.6)을 재사용한다.
KServe 0.15.2와 cert-manager 1.17.2를 설치하며, KServe의 RawDeployment 모드로
일반 Deployment/Service를 만든다. 이 버전의 RawDeployment는 최신 문서의
Standard 모드에 해당한다. 설치 스크립트는 로컬 API 주소를 확인하고, 모든 명령은
전용 kubeconfig/context를 지정한다. kubectl의 기본 context는 변경하지 않는다.

전제: chapter-5의 kind 클러스터와 kubeconfig, chapter-6 가상환경,
앞에서 빌드한 로컬 Docker 이미지 `ch6-income:lab-v2`가 있어야 한다.
아래 명령은 저장소 루트에서 실행한다.

```bash
chapter-6/.venv/bin/python chapter-6/cluster/install_kserve.py
chapter-5/.cache/bin/kind load docker-image ch6-income:lab-v2 --name ch5-lab
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab \
  apply -f chapter-6/cluster/income-service.yaml
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab \
  wait -n ch6-serving --for=condition=Ready \
  inferenceservice/income-classifier --timeout=120s
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab \
  get isvc,deploy,pod,svc -n ch6-serving
```

로컬 접근용 포트 포워딩을 별도 터미널에서 유지한다. 이미 3004 포워딩이 실행 중이면
중복 실행할 필요가 없다.

```bash
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab \
  port-forward -n ch6-serving service/income-classifier-predictor 3004:80 \
  --address 127.0.0.1
```

```bash
curl -sS http://127.0.0.1:3004/predict \
  -H 'Content-Type: application/json' \
  --data-binary @chapter-6/sample_request.json
echo
```

검증 결과: InferenceService Ready=True, Pod 1/1 Running, 기본 입력은
`{"prediction":0,"income_category":"<=50K"}`, Masters/Exec-managerial 예제는
`{"prediction":1,"income_category":">50K"}`, Education만 있는 요청은 HTTP 400이다.
생성된 Deployment의 ownerReference가 InferenceService를 가리키는 것도 확인했다.
기존 kubeflow 네임스페이스의 Deployment 14개는 모두 Ready 1/1이다.

Ingress 생성은 비활성화했다. InferenceService에 표시되는 example.com URL은
실제 접근 주소가 아니며, 이번 실습에서는 localhost:3004를 사용한다.
이미지에는 모델이 포함되어 있어 실행 시 MLflow에서 내려받지 않는다.
현재 이미지는 요청 로그 기능 추가 전 버전이다. 이미지 레지스트리/CI/GitOps 연동과
클러스터 요청의 드리프트 모니터링은 이 문서의 후반부 단계에서 구성했다.

참고: [KServe 0.15 설치 조건과 RawDeployment](https://kserve.github.io/archive/0.15/admin/kubernetes_deployment/)

<a id="registry"></a>

## 로컬 레지스트리에서 이미지 가져오기

기존 이미지로 전달 경로를 먼저 검증하는 단계다. CI/Argo CD 연결 전의 명령이며,
이미 최종 GitOps 환경을 구성했다면 이 YAML을 다시 적용하지 않는다.
레지스트리는 `localhost:5002`, 컨테이너 이름은 `ch6-registry`이며,
이미지는 Docker volume `ch6-registry-data`에 보관한다.
로컬 전용 HTTP 레지스트리이며 호스트 공개 포트는 127.0.0.1에 한정한다.

```bash
chapter-6/.venv/bin/python chapter-6/cluster/registry/setup.py
docker tag ch6-income:lab-v2 localhost:5002/ch6-income:lab-v2
docker push localhost:5002/ch6-income:lab-v2
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab \
  apply -f chapter-6/cluster/registry/income-service.yaml
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab \
  rollout status deployment/income-classifier-predictor -n ch6-serving --timeout=120s
```

매니페스트는 이번에 push한 이미지의 digest를 고정한다. 다른 이미지로 빌드했다면
push 출력의 digest로 `registry/income-service.yaml`의 image를 갱신해야 한다.
`imagePullPolicy: Always`이므로 레지스트리에 접근하지만 기존 이미지 레이어는
노드 캐시에서 재사용할 수 있다. 전체 파일을 매번 다시 받는다는 뜻은 아니다.

setup.py는 기존 kind 노드의 containerd에 registry config_path가 없을 때 추가하고
containerd를 재시작한다. localhost:5002를 컨테이너 네트워크의 ch6-registry:5000으로
연결하는 hosts.toml도 설치한다. 기본 kubectl context는 사용하지 않는다.
참고: [kind 공식 로컬 레지스트리 구성](https://kind.sigs.k8s.io/docs/user/local-registry/)

확인 결과: Kubernetes 이벤트 Successfully pulled image, 레지스트리 로그의
containerd manifest HEAD HTTP 200, InferenceService Ready=True,
샘플 예측 HTTP 200 / prediction=0을 확인했다. 기존 이미지 레이어는 캐시를 재사용했다.
기존 KFP Deployment 14개도 모두 Ready 1/1이다.
Pod 교체 시 기존 port-forward가 끊길 수 있으므로 위의 3004 포워딩 명령을 다시 실행한다.

학습 확인:

```bash
curl -sS http://localhost:5002/v2/ch6-income/tags/list
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab \
  get isvc income-classifier -n ch6-serving \
  -o jsonpath='{.spec.predictor.containers[0].image}{"\n"}'
```

<a id="gitops"></a>

## Argo CD: Git의 배포 설정을 KServe에 자동 반영

이 단계에서는 별도 로컬 Git 원격 저장소를 사용한다. 아래 publish.py는 현재 프로젝트의 Git 기록이나
GitHub 원격을 변경하지 않고 배포 전용 로컬 저장소에 커밋/푸시한다. CI 빌드 자동화는 이후 절에서 연결한다.

- 편집 대상: `chapter-6/cluster/gitops/income-service.yaml`
- 별도 작업 저장소: `chapter-6/.cache/gitops/work`
- 별도 bare 원격: `chapter-6/.cache/gitops/remote.git`
- Git 읽기 서버: Docker `ch6-git` (읽기 전용 Git daemon, 호스트 포트 공개 없음)
- Argo CD: `argocd` 네임스페이스, Application `ch6-income`, 프로젝트 `ch6-lab`

처음 구성할 때:

```bash
chapter-6/.venv/bin/python chapter-6/cluster/gitops/publish.py \
  --message 'Deploy income service through GitOps'
chapter-6/.venv/bin/python chapter-6/cluster/gitops/setup.py
```

setup.py는 Argo CD v3.6.1 공식 설치 YAML을 고정 버전으로 설치한다.
Git 서버의 Docker 네트워크 IP를 조회해 application.yaml의 REPO_URL을 치환한다.
생성한 실제 적용 YAML은 `.cache/argocd/application.yaml`에 있다.
Git 컨테이너를 재생성해 IP가 달라지면 setup.py를 다시 실행한다.
AppProject는 로컬 Git 원격과 ch6-serving의 InferenceService/Namespace만 허용한다.
자동 동기화와 selfHeal은 켜고, 리소스 삭제(prune)는 끈다.

이제 배포 설정은 `cluster/gitops/income-service.yaml`에서 수정한다.
publish.py는 이 파일만 별도 저장소에 커밋하고 로컬 원격에 push한다.
원격 저장소는 Git 프로토콜로 조회한다. push는 로컬 파일 경로로만 수행한다.
`registry/income-service.yaml`을 다시 직접 apply하면 GitOps 설정과 충돌할 수 있다.

```bash
# YAML 수정 후 실행
chapter-6/.venv/bin/python chapter-6/cluster/gitops/publish.py \
  --message 'Update serving configuration'
# 기본 주기적 조회를 기다리는 대신 즉시 Git 재조회를 요청할 수 있다.
# 아래 명령은 InferenceService를 직접 수정하는 명령이 아니다.
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab \
  annotate applications.argoproj.io ch6-income -n argocd argocd.argoproj.io/refresh=hard --overwrite
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab \
  get applications.argoproj.io -n argocd
```

UI를 볼 때 별도 터미널에서:

```bash
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab \
  port-forward -n argocd svc/argocd-server 8081:443 --address 127.0.0.1
```

`https://localhost:8081`에 접속한다. 로컬 자체 서명 인증서 경고가 표시될 수 있다.
계정은 admin이며 초기 비밀번호는 다음 명령으로 자신의 터미널에서 확인한다.

```bash
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab \
  get secret argocd-initial-admin-secret -n argocd \
  -o jsonpath='{.data.password}' | base64 --decode
echo
```

참고: [Argo CD 공식 시작 가이드](https://argo-cd.readthedocs.io/en/stable/getting_started/)

검증한 변경: Git에 `CH6_RELEASE=gitops-v1` 환경변수를 추가해 publish한 뒤,
Argo CD가 해당 커밋을 Synced/Succeeded로 반영하고 KServe가 새 Pod를 만든 것을 확인했다.
컨테이너 안의 환경변수 값과 샘플 예측 HTTP 200 / prediction=0도 확인했다.
이 환경변수는 배포 반영 확인용이며 모델의 예측 로직은 바꾸지 않는다.

```bash
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab \
  exec -n ch6-serving deployment/income-classifier-predictor -- printenv CH6_RELEASE
```

직접 반복하려면 gitops/income-service.yaml의 `gitops-v1`을 `gitops-v2`로 바꾸고
publish.py를 실행한다. Argo CD 재조회 후 새 Pod의 환경변수를 확인한다.
Pod 교체 뒤에는 예측용 port-forward를 다시 연결해야 할 수 있다.
`Application` 이름의 다른 CRD도 설치되어 있어 kubectl에서는
`applications.argoproj.io`라는 전체 리소스 이름을 사용한다.
Git 서버 이미지는 Dockerfile.git으로 빌드하며, 읽기 전용 Git daemon을 실행한다.

## 남은 운영 흐름: CI → 클러스터 모니터링 → KFP 게이트 → 롤백

이하 명령은 저장소 루트에서 실행한다. 기존 모델 저장소, 로컬 레지스트리,
KServe/Argo CD 및 5장의 KFP가 실행되어 있어야 한다.
GitHub 원격과 로컬 CI용 소스 원격, Argo CD용 배포 원격은 서로 다른 저장소다.

<a id="local-ci"></a>

### 로컬 push로 CI 실행

학습용 CI는 `ci/run.py`에 단계별로 정의되어 있다. GitHub Actions workflow나
Gitea Actions runner를 설치한 구성은 아니다. `ci/submit.py`가 필요한 소스만
`.cache/ci/work`에 복사해 커밋하고 `.cache/ci/source.git`에 push한다.
이 원격의 `post-receive` hook이 자동으로 CI를 시작한다.

```text
소스 Git push
 → 해당 커밋 checkout
 → 입력 검증·로그 실패 격리 단위 테스트
 → Bento 및 ARM64 이미지 빌드
 → 새 컨테이너의 실제 예측 0/1, 잘못된 입력 400 확인
 → 로그 파일 쓰기 실패 상태에서도 예측·stdout 기록 확인
 → 레지스트리 push
 → 배포 YAML의 이미지 digest와 release 갱신
 → 별도 배포 Git push
 → Argo CD → KServe → 새 Pod
```

```bash
chapter-6/.venv/bin/python chapter-6/ci/submit.py \
  --message 'Build monitored income service'
chapter-6/.venv/bin/python chapter-6/cluster/gitops/verify_deployment.py
```

소스가 이전 push와 같으면 새 CI 작업은 시작되지 않는다. 실패한 작업을 같은
소스 커밋으로 재실행할 때는 `ci/submit.py --retry`를 사용한다.
CI 결과는 `.cache/ci/latest.json`, 작업별 로그/결과는 `.cache/ci/jobs/`에 있다.
Git post-receive는 push 수락 후 실행되므로 **push 성공과 CI 성공은 별개**다.
submit.py는 최종 CI 상태도 확인한다. 테스트/빌드 실패 시 배포 Git 갱신 단계에는
도달하지 않는다. 빌드 이후 배포 Git push 자체가 실패했다면 작업 로그를 확인한다.

이 runner는 신뢰하는 로컬 코드만 실행하고, 현재 머신의 BentoML 모델 저장소와
가상환경/Docker를 사용한다. 작업은 파일 잠금으로 직렬화하며 push 명령은 CI가 끝날
때까지 기다린다. 운영용 인증, 분산 runner, 별도 실행 권한 경계는 구성하지 않았다.
Git hook은 네트워크 서버 프로세스가 아닌 로컬 파일 경로 push에서 실행된다.
참고: [Git post-receive hook](https://git-scm.com/docs/githooks#post-receive)

<a id="cluster-monitoring"></a>

### Kubernetes 요청 로그와 Evidently 연결

새 CI 이미지는 `CH6_LOG_STDOUT=1`일 때 성공한 예측 요청을 `CH6_REQUEST` 접두사의
JSON 로그로 기록한다. 로그에는 model_tag, model_uri, release, timestamp가 포함된다.
기존 `CH6_REQUEST_LOG` 파일 기록도 지원한다. 최대 1,000건의 큐와 별도 작업 스레드를
사용하므로 파일 쓰기 실패가 예측 요청에 전파되지 않는다. 큐가 가득 차면 기록을
버리며, 종료 시 남은 큐의 영구 저장은 보장하지 않는다.

새 Pod로 바뀌면 기존 3004 포워딩을 종료하고 다시 연결한다.

```bash
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab \
  port-forward -n ch6-serving svc/income-classifier-predictor 3004:80 --address 127.0.0.1
```

다른 터미널에서:

```bash
chapter-6/.venv-drift/bin/python chapter-6/cluster/drift_demo.py
```

실제 API로 current 1,000건, shifted 1,000건을 보낸 뒤 Kubernetes Pod 로그를 수집한다.
수집된 입력이 보낸 CSV와 일치하는지, 로그의 모델 태그/MLflow URI가 기준 데이터와
일치하는지 검사하고 각각의 보고서와 경고를 `outputs/cluster-*/`에 저장한다.
manifest에는 기준 CSV 해시, 원본 데이터/모델 정보, Pod UID, 이미지 digest도 기록한다.
마지막으로 모니터에 잘못된 기준 스키마를 넣어 실패시킨 다음, 예측 API가 계속
성공하는지 확인한다. 분석은 예측 프로세스 밖에서 실행한다.

이는 단일 Pod와 순차 트래픽에 한정한 수집 실습이다. 실행 중 다른 요청/롤아웃을
섞지 않는다. 영구 로그 수집기나 CronJob, 로그 회전·유실 복구는 구성하지 않았다.
로그 큐에서 기록이 빠지면 검증을 실패시키며, 빠진 요청을 정상 수집한 것처럼 취급하지 않는다.

<a id="kfp-gate"></a>

### KFP의 실제 조건 분기로 추론 실행/생략

Evidently는 서빙 이미지와 분리한 이미지에서 실행한다. `pipeline/build.py`는 현재
기준/현재/변형 CSV와 모델 태그를 포함한 실습용 이미지를 빌드해 레지스트리에 올린다.
데이터 또는 모델을 바꾸면 이 이미지도 다시 빌드해야 한다.

```bash
chapter-6/.venv/bin/python chapter-6/pipeline/build.py
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab \
  port-forward -n kubeflow svc/ml-pipeline 8082:8888 --address 127.0.0.1
```

다른 터미널에서 5장의 KFP SDK 환경을 사용한다.

```bash
chapter-5/.venv/bin/python chapter-6/pipeline/run_demo.py
```

두 Run의 구조는 다음과 같다.

```text
Evidently 비교(1,000건)
  ├─ Education JS < 0.1 → dsl.If → 실제 서빙 API에 10건 추론
  └─ Education JS ≥ 0.1 → dsl.Else → 추론 생략 사유 기록
```

모든 피처의 드리프트를 보고서에 저장하지만, **중단 조건은 Education 하나**로 명시했다.
Native_country의 표본 변화는 경고에 해당한다. 데이터셋 전체 드리프트 비율 0.5와도
다른 정책이다. 추론 허용 여부는 모델 성능 하락을 증명하는 판단이 아니다.

컴파일된 DAG, Run ID, KFP 작업 상태는 `outputs/kfp-gate-*/`에 저장한다.
스크립트는 current Run에서 infer가 성공하고, shifted Run에서는 infer가 성공하지
않으며 skip이 성공했는지 검사한다. 두 Run 모두 정상 종료할 수 있다.
드리프트로 의도한 추론 생략과 파이프라인 실행 오류를 구분한다.
참고: [KFP dsl.If와 dsl.Else](https://www.kubeflow.org/docs/components/pipelines/user-guides/core-functions/control-flow/)

<a id="rollback"></a>

### Git을 통한 이전 이미지 롤백과 복원

두 개의 서로 다른 CI 이미지가 성공적으로 만들어진 뒤 실행한다.
다른 CI나 드리프트 요청 전송과 동시에 실행하지 않는다.

```bash
chapter-6/.venv/bin/python chapter-6/cluster/gitops/rollback_demo.py
```

마지막 성공한 CI 기록의 이전 이미지 설정을 배포 Git에 새 커밋으로 올리고,
Argo CD 동기화·Deployment 롤아웃·환경변수·실제 예측까지 확인한다.
이어 최신 CI 이미지 설정을 다시 커밋해 복원하고 같은 검증을 반복한다.
결과는 `outputs/rollback-verification.json`에 저장한다.
Git 이력을 되쓰거나 `kubectl rollout undo`로 Git과 다른 상태를 만들지 않는다.
실습 중 배포 YAML을 별도로 수정했다면 스크립트는 덮어쓰지 않고 중단한다.

KFP 그래프를 브라우저에서 보려면 API 포트와 별도로 UI를 연결한다.
SDK가 출력하는 Run 링크는 API 주소(8082)를 사용하므로, 브라우저에서는 UI 포트(8080)를 사용한다.

```bash
kubectl --kubeconfig chapter-5/.kube/config --context kind-ch5-lab \
  port-forward -n kubeflow svc/ml-pipeline-ui 8080:80 --address 127.0.0.1
```

`http://127.0.0.1:8080`에서 chapter-6 실험의 current/shifted Run 그래프를 비교한다.

### 완료 검증 기록

| 항목 | 실행 결과 |
|---|---|
| 로컬 CI | 소스 커밋 40730fdda9d6의 push hook 실행, 단위 테스트·컨테이너 예측/400 검증·이미지 push·배포 Git 갱신 성공 |
| 로그 실패 격리 | CI 컨테이너에서 `/proc` 아래 파일 쓰기를 실패시켜도 예측 0/1과 stdout 로그 정상 |
| 클러스터 모니터링 | 실제 요청 2,000건과 CSV 일치, 경고 3건, 모델 태그/MLflow URI/기준 CSV 해시 기록 |
| 모니터 오류 격리 | 잘못된 기준 스키마로 분석 실패 후에도 예측 API 정상 응답 |
| KFP current | Education JS=0.080495, infer 실행, 실제 API 예측 10건 |
| KFP shifted | Education JS=0.597173, infer 생략, skip 작업의 사유 기록 |
| 이미지 롤백 | 이전 digest로 Git 배포 후 예측 확인, 최신 digest로 복원 후 예측 재확인 |
| 최종 상태 | Argo CD Synced/Healthy, InferenceService Ready=True, KFP Deployment 14개 Ready 1/1 |

두 KFP Run 모두 SUCCEEDED이며, 추론 생략은 의도한 정상 분기다.

- current Run ID: `2c969ebb-22ee-48e2-85c6-7e2dc19652ef`
- shifted Run ID: `2a25077f-f63e-48aa-8de3-d26394bb7597`
- 로컬 실행 기록: `outputs/kfp-gate-20261107T201917/runs.json`
- 클러스터 비교 보고서: `outputs/cluster-20261107T201400330352Z/`
- 롤백 검증: `outputs/rollback-verification.json`

실행 산출물은 Git에서 제외하며, 다른 머신에서는 앞의 명령으로 새로 생성한다.
