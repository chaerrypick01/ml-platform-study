# ML 파이프라인 도구 비교

영화 추천 모델 하나도 학습할 때는 실행 순서와 평가 점수를 기록해야 하고, 배포한 뒤에는 사용자 요청에 응답하고 그 결과를 관찰해야 한다. 도구마다 관리하는 대상이 다르다. 아래 표는 각 도구의 역할을 이 저장소에서 실제로 다룬 범위와 연결한다.

| 도구 | 동작 범위와 관리 대상 | 특장점 | 스터디에서 확인한 예 |
|---|---|---|---|
| [Kubeflow Pipelines(KFP)](https://www.kubeflow.org/docs/components/pipelines/overview/) | 데이터 준비·학습·평가·배치 추론의 작업 순서와 입출력 | 컨테이너 작업을 의존 순서대로 실행하고, 어느 단계에서 어떤 산출물이 나왔는지 추적한다. Kubeflow 프로젝트 가운데 이 역할을 맡는 구성 요소가 KFP다. | [9장](chapter-9/RESULTS.md)에서 PVC를 공유하는 학습 작업과 영화 평점 학습 작업의 실행 상태를 확인했다. |
| [Feast](https://docs.feast.dev/) | 학습·추론 입력으로 쓸 피처의 정의와 조회 | 학습 시점에 알 수 있었던 과거 피처를 조회하고, 온라인 추론 때는 사용자 키로 최신 적재값을 빠르게 읽는다. | [4장](chapter-4/experiments/feature_store/README.md)에서 MinIO의 Parquet로 과거 값을 조회하고 Redis에 적재한 사용자 피처를 온라인으로 읽었다. |
| [MLflow](https://mlflow.org/docs/latest/ml/) | 학습 실행의 파라미터·지표·아티팩트 추적, 모델 패키징·등록·서빙 | 여러 실험을 비교할 수 있고, 추론 코드와 모델 파일을 한 패키지로 묶어 표준 HTTP 엔드포인트로 실행할 수 있다. | [9장](chapter-9/RESULTS.md)에서는 학습 지표를 추적했고, [10장](chapter-10/RESULTS.md)에서는 로컬 체크포인트를 패키징해 사용자 50의 추천을 호출했다. |
| [BentoML](https://docs.bentoml.com/en/latest/) | 추론 API 구현과 배포용 패키지·이미지 제작 | 전처리, 모델, 응답 로직과 의존성을 서비스 단위로 묶는다. 개발 환경에서 확인한 처리 경로를 컨테이너에서도 실행할 수 있다. | [6장](chapter-6/README.md)에서 인코더와 소득 분류 모델을 이미지에 포함해 예측 요청을 처리했다. |
| [KServe](https://kserve.github.io/website/) | Kubernetes에서 추론 서비스의 배포와 수명 주기 관리 | 원하는 모델 서버와 이미지를 InferenceService로 선언하면 컨트롤러가 서빙 리소스를 만들고 준비 상태를 보고한다. | [6장](chapter-6/README.md)에서 BentoML 이미지를 배포한 뒤 Deployment의 소유 관계와 Ready 상태, API 응답을 확인했다. |
| [Evidently](https://docs.evidentlyai.com/) | 기준 데이터와 현재 데이터의 분포·품질 비교 | 정답이 아직 없어도 입력 분포 변화를 검사하고 그 결과를 배치 실행 여부를 결정하는 조건으로 쓸 수 있다. 드리프트만으로 정확도 하락까지 판정할 수는 없다. | [6장](chapter-6/README.md)에서 요청 로그를 1,000건씩 나눠 비교하고 KFP 검사 결과에 따라 추론 또는 건너뛰기를 선택했다. |
| [Object Storage](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html) · 실습은 MinIO | 전 단계에서 쓰는 데이터셋·모델·리포트 파일을 버킷과 객체 키로 보관 | 작업 Pod가 종료돼도 다른 작업이 같은 객체를 읽을 수 있다. 파일을 보관하는 역할과 피처 조회·실험 추적 역할을 여러 도구가 분담할 수 있다. | [4장](chapter-4/experiments/feature_store/README.md)에서 피처 원천 Parquet와 Feast 레지스트리를 보관했고, [6장](chapter-6/README.md)에서는 KFP 작업 결과를 별도 MinIO에 저장했다. |

## 같은 모델에서 역할이 갈리는 지점

- **학습 실행과 실험 비교.** 9장에서 “영화 학습 작업이 끝났나?”는 KFP의 작업 상태로 확인했다. “평균 평점만 예측하는 기준 모델보다 오차가 작았나?”는 해당 실행의 평가 지표로 확인했다. 테스트 RMSE는 기준 모델 1.0090, 학습 모델 0.9433이었다. [9장 결과](chapter-9/RESULTS.md)
- **추론 코드와 배포.** 6장의 BentoML은 요청을 받아 인코더와 모델을 실행했다. KServe는 그 이미지가 Kubernetes에서 서비스로 뜨도록 관리했다. 10장의 영화 추천에서는 MLflow가 패키징과 로컬 HTTP 서빙을 모두 맡았고, 별도로 실행한 FastAPI와 추천 세 편의 순서·점수가 일치했다. [6장 배포](chapter-6/README.md) · [10장 서빙](chapter-10/RESULTS.md)
- **서비스 상태와 데이터 품질.** 11장의 Prometheus는 추천 API 카운터를 수집했고 Grafana는 성공 요청 두 건과 미등록 사용자 요청 한 건의 증가를 보여줬다. 6장의 Evidently는 일정량의 입력을 모아 기준 분포와 비교했다. 요청이 정상 처리되는 중에도 입력 분포는 달라질 수 있어 두 관측 결과가 서로 다른 질문에 답한다. [11장 시계열](chapter-11/RESULTS.md) · [6장 드리프트 검사](chapter-6/README.md)

6장의 소득 분류와 9~11장의 영화 추천은 별개의 실습이다. 영화 추천에서는 9장의 로컬 학습 산출물로 10장 서버를 띄웠고, 11장의 Prometheus는 FastAPI 서버를 관측했다.
