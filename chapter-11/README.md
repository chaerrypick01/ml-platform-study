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
