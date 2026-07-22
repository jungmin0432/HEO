# 프론트엔드 연동 API 계약 v1

이 문서는 반응형 웹·앱 구현 담당자가 Flask 백엔드와 독립적으로 작업할 수 있게 하는 계약이다. 프론트엔드 구현 방식과 디자인은 이 저장소가 소유하지 않는다.

## 공통

- 개발 기본 주소: `http://127.0.0.1:5000`
- 응답 형식: `application/json; charset=utf-8`
- 개발 CORS: 모든 origin의 `GET`, `OPTIONS` 허용. 학교 서버 배포 전에는 실제 프론트엔드 도메인으로 제한한다.
- 모든 역사 사진 카드에는 `matching_status`, `matching_note`, `archive.attribution`을 함께 표시한다.
- PSNR, SSIM, 처리시간, 모델 비교표는 내부 검증 자료다. 이 API와 시연 UI에서 제공하지 않는다.

## 현재 제공 API

### `GET /api/v1/places`

장소 카드 목록. 지도·여정 바·장소 선택 화면의 데이터 원본이다.

```json
{
  "places": [
    {
      "id": "euljiro-line2-opening-1983-corridor",
      "title": "을지로 2호선 개통 당시 지하 연결 공간",
      "year": 1983,
      "matching_status": "REFERENCE",
      "matching_status_label": "역사 참고",
      "matching_note": "현재 사진과 1:1 비교하지 않는다.",
      "archive": {"attribution": "서울기록원, ..."}
    }
  ]
}
```

### `GET /api/v1/places/{place_id}`

선택한 장소의 전체 메타데이터. `current_reference`가 `null`이면 현재 사진 비교 UI를 숨기고 역사 참고 안내만 표시한다.

### `GET /assets/history/{place_id}`

선택한 장소의 원본 역사사진. `<img>`의 `src`로 사용할 수 있다. 결과물에는 `archive.attribution`과 출처 링크를 함께 표시한다.

### `GET /api/v1/restorations`

이미 생성된 복원기록 목록. 현재는 개발자가 실행한 기준선 결과를 반환한다.

## 다음 단계에서 제공할 API

| API | 요청 | 응답 | 프론트엔드 역할 |
| --- | --- | --- | --- |
| `POST /api/v1/restorations` | 원본 파일 또는 `place_id`, 복원 강도 | `record_id`, 처리 상태 | 업로드·복원 시작 |
| `GET /api/v1/restorations/{record_id}` | 없음 | 결과 이미지 URL, 신뢰기록, 경고 | 결과 비교 화면 |
| `GET /api/v1/restorations/{record_id}/card` | 없음 | 인쇄·공유용 복원기록 카드 데이터 | 기념품·점포 요청 화면 |

정량평가 결과는 `benchmarks/`의 CSV·JSON 파일로만 보관하며, 위 API에 포함하지 않는다.

## 화면이 반드시 지켜야 할 표현

- `REFERENCE`: “을지로의 역사 참고 사진”으로 표기. “같은 장소의 과거”라고 단정하지 않음.
- `NEARBY`: “을지로 생활권의 현재 참고”로 표기. “정확히 같은 촬영 지점”이라고 단정하지 않음.
- `EXACT`: 운영자가 랜드마크·시점 확인을 완료한 경우에만 사용.
- AI 또는 강한 보정 결과에는 원본, 복원 강도, 처리 모델, 경고문을 함께 보여 줌.
