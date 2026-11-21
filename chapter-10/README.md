# Chapter 10 — 영화 추천 모델 서빙

9장에서 학습한 MovieLens 평점 예측 모델을 FastAPI로 띄웠다. 사용자 50의 학습 이력에 있는 영화를 후보에서 제외하고, 남은 영화의 예측 평점이 높은 순으로 세 편을 반환한다. 모델이 아는 영화만 후보에 들어간다.

## 시작하기

저장소 루트에서 실행한다. 9장의 가상환경과 로컬 학습 산출물 `chapter-9/outputs/movie-local/{model.pt,movielens.zip,result.json}`을 사용한다. 산출물이 없는 환경에서는 [9장 실행 안내](../chapter-9/RUNBOOK.md)의 영화 학습 명령에서 출력 경로를 `chapter-9/outputs/movie-local`로 지정한다. 체크포인트는 직접 학습한 파일을 사용한다.

```sh
chapter-9/.venv/bin/python -m uvicorn serve:app --app-dir chapter-10 --host 127.0.0.1 --port 18857
```

다른 터미널에서 호출한다.

```sh
curl -i http://127.0.0.1:18857/users/50/recommendations
```

## 실습 결과

측정값과 배운 점은 [실습 결과](RESULTS.md)에 정리했다.

## 도전과제 · MLflow로 영화 추천 호출하기

같은 추천 코드를 MLflow의 PythonModel로 감쌌다. 패키지에 체크포인트, 평점 데이터, 학습 메타데이터를 포함해 서버가 시작될 때 함께 읽도록 했다. 저장소 루트에서 실행한다. 모델 출력 경로는 처음 실행할 때 비어 있어야 한다.

```sh
source chapter-9/.venv/bin/activate
export MLFLOW_TRACKING_URI="file://$PWD/chapter-9/outputs/mlruns"
python chapter-10/package_model.py chapter-9/outputs/mlflow-recommendations
python -m pip install --no-deps --target chapter-9/outputs/mlflow-serving-deps fastapi==0.115.12 starlette==0.46.2
PYTHONPATH="$PWD/chapter-9/outputs/mlflow-serving-deps" mlflow models serve \
  -m "$PWD/chapter-9/outputs/mlflow-recommendations" --env-manager local --host 127.0.0.1 --port 18858
```

MLflow 3.0.0의 추론 서버는 기존 환경의 FastAPI 0.162.7에서 시작할 때 `FastAPI.route` 오류가 났다. 위 명령은 호환 버전을 서버 프로세스에만 적용한다. 다른 터미널에서 호출한다.

```sh
curl -i http://127.0.0.1:18858/invocations -H 'Content-Type: application/json' \
  -d '{"dataframe_records":[{"user_id":50}]}'
```
