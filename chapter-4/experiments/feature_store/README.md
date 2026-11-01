# CH4 로컬 Feast · MinIO · Redis 실습

교재는 서버가 별도로 설치되어 있다고 가정한다. 여기서는 Docker Compose로 실습 전용 서버를 띄우고, PC의 `venv`에서 Feast를 실행한다. 원본 `feast/` 설정과 다른 프로젝트의 서비스는 수정하지 않는다.

## 구성

| 구성 | 주소 | 역할 |
|---|---|---|
| MinIO S3 API | http://127.0.0.1:19000 | 피처 원천 Parquet와 Feast Registry 저장 |
| MinIO Console | http://127.0.0.1:19001 | 버킷·파일 확인 |
| Redis | 127.0.0.1:16379 | 사용자별 온라인 피처 저장 |
| Feast | PC의 Python/CLI | 정의 등록, 과거 조회, 적재, 온라인 조회 |

MinIO 로그인은 `ch4local` / `ch4-local-only-password`다. Redis 비밀번호는 `ch4-local-redis`다. 모두 이 실습 전용 값이며 포트는 localhost에만 바인딩한다.

이미지는 현재 Mac의 ARM64 이미지 digest로 고정했다. 다른 CPU 환경으로 옮기면 적합한 멀티아키텍처 이미지 참조로 변경해야 한다.

## 실행 순서

VS Code에서는 같은 폴더의 `feature_store_lab.ipynb`를 열고 **Python (chapter-4 venv)** 커널을 선택해 셀별로 실행할 수 있다.

아래 명령은 `chapter-4` 폴더에서 실행한다. Python 패키지는 기존 `venv`의 Feast 0.40.1을 사용한다.

```bash
docker compose -f experiments/feature_store/compose.yaml up -d --wait
venv/bin/python experiments/feature_store/run_lab.py prepare
venv/bin/python experiments/feature_store/run_lab.py apply
venv/bin/python experiments/feature_store/run_lab.py historical
venv/bin/python experiments/feature_store/run_lab.py materialize
venv/bin/python experiments/feature_store/run_lab.py online
```

| 단계 | 동작 | 검증 |
|---|---|---|
| prepare | 시간 필드를 UTC로 명시한 사본 생성, 파일 3개 업로드 | 내려받은 파일의 SHA-256이 업로드 사본과 일치 |
| apply | `feast apply`, Registry를 MinIO에 저장 | FeatureView 3개 등록, Redis 키 개수 확인 |
| historical | MinIO 원천에서 시점별 피처 조회 | 사용자 5명의 8개 값 일치, 원천 이전 시점은 모두 null |
| materialize | 원천의 시간 범위를 읽어 Redis에 적재 | 적재 기간과 Redis 키 개수 기록 |
| online | 사용자 ID로 Redis의 피처 조회 | 사용자 5명의 8개 값이 원천과 일치 |

첫 실행에서 apply만 수행하면 Redis에 피처 값이 없다. materialize가 실제 값을 넣는다. 재실행 시 기존 Redis 값이 남아 있으므로 apply 직후의 키 개수도 0이 아닐 수 있다. 스크립트는 기존 값을 삭제하지 않는다.

`all`을 사용하면 다섯 단계를 순서대로 다시 실행한다. 단계별 JSON 검증 결과와 조회 CSV는 `experiments/outputs/feature-store/`에 저장하며 재실행 시 덮어쓴다.

## 확인할 내용

원본 Parquet의 시간 필드에는 시간대가 없다. 이 실습에서는 UTC로 해석한 사본을 업로드한다. 원본 파일은 수정하지 않는다. Feast 0.40.1에서 원천 이전 시점을 조회할 때 발생했던 timezone-naive/aware 비교 오류를 피하면서, 실제 값이 없는 경우 null이 반환되는지도 확인한다.

```text
PC의 Client / Feast
  ├─ apply → MinIO의 Registry에 피처 정의 저장
  ├─ historical → MinIO의 과거 피처를 조회
  ├─ materialize → MinIO에서 읽고 Redis에 적재
  └─ online → Redis에서 사용자별 피처 조회
```

원천은 과거 실습 데이터다. 온라인 조회는 마지막으로 적재한 최신값이며, 오늘 시점의 실제 데이터라는 의미가 아니다. 이 데이터는 사용자당 피처 이력이 제한적이므로 원천 이전 시점의 null 검증이 복잡한 지연 도착·보정 시나리오까지 검증하지는 않는다.

이 단계에서는 모델을 다시 학습하거나 추론하지 않는다. 앞서 만든 MLflow 모델은 여전히 CSV로 학습한 모델이며, MLflow 아티팩트도 로컬에 남아 있다. Feast 피처를 모델 입력으로 연결하는 작업과 MLflow 아티팩트를 MinIO에 저장하는 작업은 별도다.

## 중지·재시작

```bash
docker compose -f experiments/feature_store/compose.yaml stop
docker compose -f experiments/feature_store/compose.yaml start
```

서비스 데이터는 전용 Docker volume에 보관한다. `down`은 컨테이너와 네트워크를 제거하지만 volume은 유지한다. `down -v`는 실습 데이터를 삭제하므로 재설정이 필요할 때만 사용한다.
