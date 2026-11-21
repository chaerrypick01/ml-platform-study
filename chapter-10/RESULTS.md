# Chapter 10 — 영화 추천 모델 서빙 실습 결과

HTTP 200을 받았다. 로컬 추론에서 확인한 세 영화의 순서와 소수점 셋째 자리까지의 점수가 API 응답과 일치했다. [실제 응답](results/user-50.json)

| 순위 | 영화 | 예측 평점 |
|---|---|---:|
| 1 | The Princess Bride | 3.948 |
| 2 | The Return of the King | 3.913 |
| 3 | Seven Samurai | 3.829 |

같은 추천을 재현하려면 가중치와 함께 사용자·영화 ID 매핑, 학습 당시의 시청 이력에 해당하는 평점 데이터, 후보 제외 규칙까지 서빙 환경에서 복원해야 한다. 이번 비교로 확인한 것은 로컬 추론과 API의 일치 여부다. 실제 사용자 선호에 맞는지는 별도 평가가 필요하다.

## MLflow 서빙 도전과제

MLflow 3.0.0으로 패키징한 로컬 모델을 실행했다. 준비 상태 확인(GET /ping)과 사용자 50 추천 요청(POST /invocations)이 모두 HTTP 200을 반환했다. 응답의 predictions 첫 항목을 기존 FastAPI 응답과 대조해 사용자 ID와 세 영화의 ID·제목·순서·점수가 모두 일치함을 확인했다. [MLflow 원본 응답](results/mlflow-user-50.json)

FastAPI 실습에서는 URL과 응답 형식을 직접 정의했다. MLflow에서는 입력 스키마와 predict 함수를 담은 모델 패키지를 만들면 기본 추론 서버가 HTTP 요청을 받아 predict에 전달한다. 이번 배포는 로컬 패키지 경로를 사용했다.
