# 현재 사진-과거 기록 연결 API

## 목적과 범위

이 API는 현재 사진을 공개 기록 사진과 **후보 검색** 수준에서 연결한다. 반환되는 점수는 동일 촬영 지점의 확률이나 역사적 사실의 증명이 아니다. 사진 구조, 입력 GPS, 주변 장소 단서를 조합해 후보를 정렬하고, 근거와 한계를 함께 반환한다.

- 기본 로컬 주소: `http://127.0.0.1:5050`
- CORS: 개발용으로 `*` 허용. 실제 배포 전에는 공통 프론트엔드 도메인으로 제한한다.
- 입력 사진: JPG, PNG, WebP, 15MB 이하
- 업로드한 후보 검색용 원본은 처리 완료 후 서버 임시 폴더에서 삭제한다.
- 기록별 위치는 검증된 촬영점이 아니라 공식 역 좌표를 바탕으로 한 **역세권 앵커**다. [서울시 역사 좌표 데이터](https://data.seoul.go.kr/dataList/OA-22534/F/1/datasetView.do)를 보조 범위 정보로 사용한다.

## 상태 확인

### `GET /api/v1/location-matching/status`

모델을 메모리에 올리지 않고 캐시와 인덱스의 준비 상태만 확인한다.

```json
{
  "available": true,
  "asset_count": 56,
  "anchored_asset_count": 56,
  "coordinate_policy": "station_area_anchor_only",
  "clip_model": "openai/clip-vit-base-patch32",
  "dino_model": "facebook/dinov2-small"
}
```

## 기록 후보 찾기

### `POST /api/v1/location-matches`

`multipart/form-data`로 요청한다.

| 필드 | 형식 | 필수 | 설명 |
| --- | --- | --- | --- |
| `photo` | 파일 | 예 | 현재 사진 |
| `latitude` | number | 아니오 | 위도. 경도와 함께 입력 |
| `longitude` | number | 아니오 | 경도. 위도와 함께 입력 |
| `gps_accuracy_m` | number | 아니오 | 기기 표시 정확도(m), 0~10,000 |
| `landmark_text` | string | 아니오 | 역명, 출입구, 통로 등 직접 입력한 단서 |
| `limit` | integer | 아니오 | 1~10, 기본 5 |

```javascript
const data = new FormData();
data.append("photo", file);
data.append("latitude", "37.56629");
data.append("longitude", "126.99278");
data.append("gps_accuracy_m", "60");
data.append("landmark_text", "을지로3가역 지하 연결 통로");
data.append("limit", "3");

const response = await fetch(`${apiBase}/api/v1/location-matches`, {
  method: "POST",
  body: data,
});
const result = await response.json();
```

응답의 핵심 구조:

```json
{
  "decision": "CANDIDATES",
  "decision_note": "후보는 기록 탐색을 돕는 순위이며 동일 촬영 지점을 확정하지 않습니다.",
  "input_summary": {"gps_used": true, "gps_accuracy_m": 60, "landmark_text": "을지로3가역 지하 연결 통로"},
  "candidates": [
    {
      "rank": 1,
      "asset_id": "...",
      "asset_url": "/assets/archive/...",
      "title": "공개 기록 제목",
      "year": 1983,
      "retrieval_score": 86.4,
      "confidence_band": "high",
      "evidence": [
        {"label": "사진 구조", "description": "DINOv2 구조 검색 1위, CLIP 장면 검색 2위"},
        {"label": "입력 위치", "description": "입력 좌표에서 역세권 앵커까지 약 54m (정확한 과거 촬영점 아님)"}
      ],
      "limitations": ["후보 검색 점수는 동일 장소일 확률이나 역사적 사실의 증명이 아닙니다."]
    }
  ]
}
```

`HOLD`는 입력 단서가 부족하거나 상위 후보 근거가 약하다는 뜻이다. 이 경우 UI는 후보를 강하게 추천하지 말고 GPS·주변 장소의 보완 입력을 안내한다.

## 복원으로 넘기기

후보 상세에서 사용자가 기록을 직접 선택한 경우에만, 기존 복원 API에 `matched_asset_id`를 추가한다.

### `POST /api/v1/restorations`

```javascript
const form = new FormData();
form.append("source_mode", "upload");
form.append("photo", currentPhoto);
form.append("matched_asset_id", selectedCandidate.asset_id);
form.append("use_ai", "true");
```

응답의 `historical_context`에 선택한 공개 기록의 제목, 연도, 출처, `asset_url`, 매칭 한계가 남는다. 프론트엔드는 이 정보를 결과 화면의 ‘기록 연결’ 영역에 표시한다.

## 오류와 화면 처리

| 상태 | API 의미 | UI 처리 |
| --- | --- | --- |
| 400 | 사진 누락, 형식 오류, 좌표 쌍 누락 | 입력 필드 아래에 수정 안내 |
| 503 | 로컬 모델 런타임 또는 사전학습 가중치 미준비 | ‘후보 찾기를 잠시 사용할 수 없음’ 표시, 사진 복원은 계속 가능 |
| `decision=HOLD` | 모델 오류가 아닌 근거 부족 | 후보 확정 표현 금지, 단서 보완 유도 |

원시 cosine 점수, 모델별 임베딩, 실험 지표는 사용자 화면에 노출하지 않는다. 정량 평가는 `benchmarks/location_matching/`의 CSV와 별도 실험 문서에서 관리한다.
