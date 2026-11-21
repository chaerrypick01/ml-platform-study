# Chapter 11 — 추천 요청 모니터링

API가 떠 있어도 학습에 없던 사용자는 개인화 추천을 받을 수 없다. 10장 서버에 등록 사용자와 미등록 사용자 요청을 하나씩 보내 어떤 차이가 지표에 남는지 확인했다.

## 시작하기

[10장 실행 안내](../chapter-10/README.md)에 따라 단일 워커 서버를 새로 띄운 뒤 순서대로 호출한다.

```sh
curl -s http://127.0.0.1:18857/metrics
curl -i http://127.0.0.1:18857/users/50/recommendations
curl -i http://127.0.0.1:18857/users/999999/recommendations
curl -s http://127.0.0.1:18857/metrics
```

## 실습 결과

측정값과 배운 점은 [실습 결과](RESULTS.md)에 정리했다.

## Prometheus 수집과 Grafana 시각화

10장 FastAPI 서버를 실행한 Mac의 Docker Desktop에서 아래 명령을 실행한다. Compose의 Prometheus가 호스트의 추천 API를 5초마다 읽고, Grafana는 같은 Prometheus를 데이터 소스로 사용한다. 로컬 단일 API의 주소를 직접 지정하므로 Kubernetes PodMonitor는 사용하지 않는다.

```sh
cd chapter-11
docker compose up -d
```

[Prometheus 수집 대상](http://127.0.0.1:18859/targets)에서 movie-recommendations가 UP인지 확인한다. [Grafana 영화 추천 대시보드](http://127.0.0.1:18860/d/movie-recommendations)에서 결과별 누적 요청 수를 볼 수 있다. 두 화면 모두 이 Mac에서 접속한다.

첫 수집 후 아래 검증을 실행한다. 사용자 50을 두 번, 미등록 사용자를 한 번 호출하고 Prometheus 카운터 증가량과 Grafana 패널 쿼리의 시계열을 대조한다. 실행하는 동안 다른 추천 요청이 들어오면 증가량이 달라질 수 있다.

```sh
python3 verify_monitoring.py
```

실습을 마치면 이 디렉터리에서 `docker compose down`으로 모니터링 컨테이너를 종료할 수 있다.
