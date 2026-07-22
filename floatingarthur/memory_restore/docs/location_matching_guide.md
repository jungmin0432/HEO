# 기록 후보 검색 운영·개발 가이드

## 구성

| 경로 | 역할 |
| --- | --- |
| `data/archive_index.json` | 공개 기록별 출처, 역세권 앵커, 태그, 검증 수준 |
| `cache/location_matching/` | 56장 기록의 CLIP·DINOv2 사전 계산 특징 |
| `cache/huggingface/` | 로컬 전용 사전학습 모델 가중치 |
| `services/location_matching.py` | 질의 사진 특징 추출, GPS·태그 결합 정렬 |
| `app.py` | 후보 검색·기록 자산·복원 연결 API |
| `ui_prototype/` | 공통 UI 이식 전 검증용 반응형 데모 |
| `benchmarks/location_matching/` | 사용자 화면에 노출하지 않는 정량 평가 실험 기록 |

## 실행

```powershell
cd C:\Users\ktc system\나\3-1\경진대회\memory_restore
powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1 -Port 5050
```

- 데모 화면: `http://127.0.0.1:5050/prototype`
- API 상태: `http://127.0.0.1:5050/api/v1/location-matching/status`
- 기본 바인딩은 `127.0.0.1`뿐이다. 외부 접근을 열지 않는다.
- 첫 후보 검색은 CLIP·DINOv2 모델을 로컬 메모리에 올리므로 이후 요청보다 느릴 수 있다.

## 캐시와 인덱스 갱신

공개 기록 사진을 추가하거나 모델을 변경한 경우에만 다음 순서로 다시 만든다.

```powershell
.\.venv\Scripts\python.exe scripts\build_archive_index.py
powershell -ExecutionPolicy Bypass -File scripts\build_location_feature_cache.ps1
```

인덱스의 사진 순서와 `manifest.json`의 사진 순서는 반드시 같아야 한다. API는 두 순서가 다르면 시작 단계에서 오류를 낸다.

## 좌표·태그 작성 규칙

- 개별 사진의 정확한 촬영점이 공식 기록으로 확인되지 않은 경우 `station_area_anchor`만 쓴다.
- 역세권 앵커는 사진 촬영점처럼 화면에 표현하지 않는다.
- 장소 태그는 원문 출처·공식 지도 자료로 확인한 것만 넣는다.
- 출처 없는 추정 좌표, 사용자 입력을 장기 인덱스에 반영하지 않는다.

## 모델과 한계

현재 구현은 DINOv2 ViT-S/14와 CLIP ViT-B/32의 사전학습 특징을 사용한다. 질의 사진에서 두 특징을 계산하고 캐시된 56장 특징과 비교한다. GPS와 텍스트 단서는 있을 때만 가중치를 재분배한다.

문서의 장기 계획에 포함된 DISK + LightGlue 국소 특징 검증은 아직 구현하지 않았다. 따라서 결과에는 해당 사실을 한계로 표시한다. 모델 가중치·점수·임베딩은 UI에 노출하지 않는다.

## 정량 평가 원칙

부트캠프 평가 기준에 맞춰, 성과를 주장하기 전 비교군과 실패 기준을 먼저 고정했다. 상세한 기준은 [02_location_match_service_concept.md](02_location_match_service_concept.md), 구현 범위는 [03_location_match_integration_plan.md](03_location_match_integration_plan.md)를 따른다.

- 비교군: DINOv2 단독, CLIP 단독, 두 모델 앙상블, GPS·장소 단서 결합
- 사전 성공 조건: Recall@3, nDCG@5, 강한 추천 구간의 실제 적중률, p95 응답 시간, 출처 연결률
- 실행 기록: `benchmarks/location_matching/experiment_template.csv`
- 현 단계에서는 독립 라벨이 충분하지 않아 모델 우위나 정확도를 주장하지 않는다.

## 점검

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

후보 검색의 실제 모델 호출은 사전학습 가중치와 CPU/GPU 환경 영향을 받으므로, 자동 단위 테스트에서는 상태·입력 검증·복원 연결만 검사한다. 데모 전에는 실제 공개 사진 1장, GPS·장소 단서가 있는 입력으로 `POST /api/v1/location-matches`를 수동 점검한다.
