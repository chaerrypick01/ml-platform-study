# 과제용 소득 분류 실험

질문: 다수 클래스만 예측하는 기준 모델보다 학습한 모델이 얼마나 좋아질까?
추가 관찰: 의사결정나무의 깊이를 제한하면 학습과 검증 성능의 차이가 줄어들까?

## 실행

`chapter-4` 폴더에서 다음 명령을 실행한다.

```bash
venv/bin/python experiments/income_experiment.py
```

VS Code에서는 `income_experiment.ipynb`를 열고 커널로 `chapter-4/venv/bin/python`을 선택한다.
실행할 때마다 별도의 결과 폴더와 MLflow run이 생성된다.

## 실험 조건

- 데이터: `data/income_data.csv`, 정답은 `>50K` 여부
- CSV 범주 값의 앞뒤 공백 제거
- 기준 모델, 깊이 5의 의사결정나무, 깊이 제한 없는 의사결정나무, 랜덤 포레스트 비교
- 시드 42, 정답 비율을 유지해 학습/검증/테스트를 약 60/20/20으로 분리
- 원-핫 인코더는 학습 데이터로만 학습, 처음 보는 범주는 무시
- 검증 ROC AUC로 후보를 선택한 뒤 학습+검증 데이터로 재학습
- 선택한 모델만 테스트 데이터로 최종 평가
- 전처리와 모델을 함께 저장하고 다시 불러와 예측 일치 확인

정확도 외에 ROC AUC, average precision, precision, recall, F1을 확인한다.
낮은 소득 클래스가 다수이므로 정확도만으로 모델을 평가하지 않는다.
무작위 분할 한 번의 결과이며, 통계적 우월성이나 실제 서비스 성능을 입증하는 실험은 아니다.
동일한 입력값의 서로 다른 행이 있을 수 있으므로, 데이터 중복과 개체별 분할은 후속 검토 대상이다.

## 결과 확인

```bash
venv/bin/mlflow ui --backend-store-uri "sqlite:///$(pwd)/experiments/outputs/mlflow.db" --host 127.0.0.1 --port 5001
```

브라우저에서 http://127.0.0.1:5001 을 열고 `assignment-income-classification` 실험을 선택한다.
`phase=candidate`는 후보 비교, `phase=final`은 최종 테스트다.
Models에는 `assignment-income-classifier`가 등록된다.

`outputs/<실행시각>/`에 다음 결과가 생성된다.

- `comparison.csv`: 후보별 학습·검증 성능
- `model_comparison.png`: 학습·검증 ROC AUC 비교 그래프
- `test_confusion_matrix.png`: 최종 모델의 오분류 분포
- `result.json`: 선택 모델, 테스트 성능, 재로딩 검증 결과
- `manifest.json`, `split_rows.csv`, `requirements-lock.txt`: 데이터 해시·분할·환경 기록

## 제출 글에 담을 내용

1. 실험 질문과 비교 조건
2. 정확도만으로 평가하기 어려운 이유
3. 후보별 검증 점수와 과적합 관찰
4. 선택 모델의 테스트 성능, 혼동 행렬, MLflow 화면
5. 발견한 한계와 다음 실험

## CH4·CH5와의 관계

이 실험은 CH4의 모델 비교·실험 추적·등록을 로컬에서 수행한다.
Feast, Redis, Kubernetes, CH5 파이프라인은 아직 연결하지 않는다.
기존 교재의 MLflow 서버와 별도의 로컬 DB 및 모델 이름을 사용한다.
CH5로 확장할 때는 공유 MLflow 서버, Feast 피처 조회, 클러스터 접근 주소를 설정해야 한다.
현재 모델은 전처리를 포함하므로 CH5 추론 코드도 원본 범주형 열을 전달하도록 맞춰야 한다.
