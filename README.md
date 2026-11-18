# ml-platform-study

ML 플랫폼 학습 노트와 로컬 실습 기록을 정리한 저장소다.

## 챕터 목차

| 챕터 | 내용 | README |
|---|---|---|
| Chapter 1 | MLOps와 ML 엔지니어링의 시작 | [학습 노트](chapter-1/README.md) |
| Chapter 2 | MLOps의 역할과 모델 평가 | [학습 노트](chapter-2/README.md) |
| Chapter 3 | 컨테이너·배포·모니터링 | [학습 노트](chapter-3/README.md) |
| Chapter 4 | MLflow 실험 관리와 Feast 피처 스토어 | [챕터 안내](chapter-4/Readme.md) · [로컬 실험](chapter-4/experiments/README.md) · [Feast 실습](chapter-4/experiments/feature_store/README.md) |
| Chapter 5 | 로컬 kind에서 KFP 배치 추론 | [실습 안내와 결과](chapter-5/README.md) |
| Chapter 6 | BentoML 서빙, KServe·Argo CD 배포, CI와 드리프트 게이트 | [실습 안내와 결과](chapter-6/README.md) |
| Chapter 7 | 공개 데이터 준비, 분할 QA, KFP 아티팩트 전달 | [학습 노트](chapter-7/README.md) · [아키텍처](chapter-7/README.md#아키텍처) |
| Chapter 8 | YOLO 학습·검증, 체크포인트와 CPU/MPS 비교 | [학습 노트](chapter-8/README.md) · [아키텍처](chapter-8/README.md#아키텍처) |
| Chapter 9 | PVC, TensorBoard, MLflow, 영화 평점 예측 | [학습 노트](chapter-9/README.md) · [아키텍처](chapter-9/README.md#아키텍처) · [실행 안내](chapter-9/RUNBOOK.md) |

실습은 Chapter 4에서 모델과 피처를 준비한 뒤, Chapter 5에서 이를 KFP 파이프라인으로 연결하는 순서로 진행한다. Chapter 6에서는 같은 모델과 로컬 클러스터를 사용해 서빙·자동 배포·드리프트 감지·롤백을 실습한다.

Chapter 7~9에서는 기존 로컬 KFP를 재사용해 공개 객체 탐지 데이터의 준비·학습·검증을 연결하고, PVC·학습 추적과 Mac CPU/MPS 비교를 실습한다. 이전 장의 소득 분류 모델은 다시 학습하지 않는다.
