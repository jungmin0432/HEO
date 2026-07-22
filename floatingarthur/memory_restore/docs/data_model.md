# 데이터 모델 초안

## 장소 카드 (`places.json`)

| 필드 | 목적 |
| --- | --- |
| `id` | URL·복원기록에 쓰는 고정 식별자 |
| `historical_asset_path` | `../photos` 아래 원본 사진의 상대 경로 |
| `archive` | 기록명·기록번호·날짜·출처·표기 문구 |
| `matching_status` | `EXACT`, `NEARBY`, `REFERENCE` 중 하나 |
| `matching_note` | 비교의 한계를 사용자에게 설명하는 문장 |
| `current_reference` | 현재 참고 사진과 출처. 없으면 `null` |

## 향후 복원 기록 (`restoration_record.json`)

복원 결과는 아래 항목을 반드시 보관한다. 원본은 수정·덮어쓰기하지 않는다.

```json
{
  "record_id": "uuid",
  "created_at": "ISO-8601 timestamp",
  "source_type": "archive | personal",
  "place_id": "optional place card id",
  "original_filename": "source.jpg",
  "original_sha256": "hash",
  "input_resolution": "width x height",
  "output_resolution": "width x height",
  "restoration_mode": "preserve | conservative | expressive",
  "pipeline": [{"name": "opencv", "settings": {}}],
  "warnings": ["AI가 추정한 세부 묘사가 포함될 수 있습니다."],
  "ai_marked": true,
  "intended_print_size": "optional",
  "source_attribution": "required for archive"
}
```
