# 공통 UI 이식 가이드: 기록 찾기

## 프론트엔드 독립 원칙

현재 `ui_prototype/`은 Flask가 제공하는 데모 화면일 뿐, 공통 UI의 라우팅·상태관리·컴포넌트 체계를 강제하지 않는다. 다른 웹 또는 앱 UI는 [location_matching_api.md](location_matching_api.md)의 두 API만 사용하면 된다.

1. 공통 UI가 파일을 선택하고 화면 미리보기를 만든다.
2. 선택 입력인 GPS와 주변 장소 단서를 수집한다.
3. `POST /api/v1/location-matches`를 호출한다.
4. 후보 목록은 정렬 결과, 상세는 근거와 한계를 표시한다.
5. 사용자가 후보를 직접 선택할 때만 `matched_asset_id`를 복원 요청에 전달한다.

`apiBase`를 분리한다. 예를 들어 독립 개발 서버에서는 `http://127.0.0.1:5050`을 API base로 두고, 배포 시 환경 변수로 교체한다. API는 상대 경로 `asset_url`을 주므로 이미지 주소는 `new URL(asset_url, apiBase)`로 만든다.

## 권장 상태 모델

```text
idle
  -> photo_selected
  -> searching
  -> candidates | hold | request_error
candidates
  -> candidate_detail
candidate_detail
  -> restoration_handoff
```

- `photo_selected`: 사진 없이는 조회 버튼을 활성화하지 않는다.
- `searching`: 중복 호출을 막고 취소·뒤로 가기를 제공한다.
- `hold`: 실패처럼 보이지 않게 ‘단서 보완’ 상태로 표현한다.
- `restoration_handoff`: 선택 후보의 `asset_id`와 현재 사진만 넘긴다. API 응답의 점수를 재계산하지 않는다.

## 표시 원칙

- 점수 문구: `후보 적합도` 또는 `후보 검색 점수`
- 금지 문구: `동일 장소 확정`, `과거 위치 판별 완료`, `정확도 86%`
- 근거는 반드시 후보별 `evidence` 배열에서 출력한다.
- `limitations`는 접지 말고 상세 화면에서 항상 읽을 수 있게 둔다.
- 출처 링크는 `candidate.archive.source_url`을 사용하고 새 창 또는 앱 내 웹뷰에서 연다.
- GPS는 지하에서 불안정하므로 필수 입력으로 만들지 않는다. 위도만 또는 경도만 입력한 경우 API가 400을 반환하므로 UI에서 사전 검증한다.

## 모바일 정보 구조

홈은 스크롤을 유지해도 되지만, 핵심 탐색은 전체 화면의 하위 흐름으로 분리한다.

| 깊이 | 화면 | 주된 행동 |
| --- | --- | --- |
| 상위 | 여정 홈 | 기록 탐색 진입, 네 구역 맥락 확인 |
| 1단계 | 현재 장면 입력 | 사진, GPS, 장소 단서 입력 |
| 2단계 | 후보 목록 | 상위 3개를 비교 |
| 3단계 | 후보 상세 | 출처·근거·한계 확인 후 복원으로 넘김 |
| 상위 | 복원 작업 | 선택 기록을 맥락으로 보존형 복원 |

이 구조는 휴대폰에서 긴 스크롤 중 입력 맥락을 잃지 않게 하면서도, 기존 공통 UI의 탭·스택·모달 어느 방식에도 옮길 수 있다.

## 데모 프로토타입 위치

- 화면: `/prototype`
- 정적 파일: `ui_prototype/index.html`, `ui_prototype/assets/styles.css`, `ui_prototype/assets/app.js`
- 실행: `powershell -ExecutionPolicy Bypass -File scripts/run_local.ps1 -Port 5050`

프로토타입은 사용자 상태를 브라우저 메모리에서만 보관한다. 공통 UI가 세션 저장을 도입하더라도 GPS·사진은 동의 없이 장기 보관하지 않는다.
