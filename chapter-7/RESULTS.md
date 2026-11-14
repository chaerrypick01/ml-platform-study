# Chapter 7 — 실습 결과

환경 분리 전 실행한 증거를 이 장에서 찾아볼 수 있도록 정리했다. 환경 분리 후 재검증 내역은 별도로 표시한다.

COCO128 96/16/16장 분할과 이미지·라벨 해시 검사를 통과했다. MovieLens 준비·QA Run `be7bc159-b134-4fcf-b817-f345c0b486ca`는 성공했다.

- [COCO128 QA](results/data-qa.json)
- [MovieLens QA](results/movielens-data-qa.json)

통합 실습 당시의 상세 설명은 [기존 7~9장 기록](../chapter-9/RESULTS.md)에 보존했다.

## 환경 분리 후 검증

새 가상환경에서 COCO128을 다시 준비했고 기존 manifest와 일치했다. torch·ultralytics 없이 실행했다. 전용 `ch7-data:v1` 이미지도 빌드하고 MovieLens 준비·QA 함수를 실제 컨테이너에서 실행해 통과했다. 새 KFP Run 제출은 수행하지 않았다.

[환경 검증 기록](results/environment-check.json)
