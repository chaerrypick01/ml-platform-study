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
