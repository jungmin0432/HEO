# AI 시간제작소 로컬 개발 가이드

## 1. 개발 원칙

- 현재 단계에서는 로컬 컴퓨터에서만 API와 모델을 실행한다.
- Flask는 `127.0.0.1`에만 바인딩한다. `0.0.0.0`, 포트 포워딩, 터널링, 외부 공유 URL은 사용하지 않는다.
- 화면은 다른 팀원의 반응형 웹과 결합한다. 이 폴더는 Flask API와 사진 복원 로직만 담당한다.
- 외부 GPU 서버는 배포 대상이 아니라, 나중에 관리자 승인을 받은 뒤 같은 폴더 구조로 복사하는 대상이다.

## 2. 필요한 폴더 위치

```text
C:\Users\ktc system\나\3-1\경진대회\
  memory_restore\
  photos\
```

두 폴더는 반드시 형제 위치여야 한다. `memory_restore\app.py`는 기본적으로 `..\photos`에서 공개 역사 사진과 현재 참조 사진을 읽는다.

## 3. 처음 한 번만 하는 로컬 준비

PowerShell에서 다음 위치로 이동한다.

```powershell
cd 'C:\Users\ktc system\나\3-1\경진대회\memory_restore'
```

가상환경이 없다면 만든 뒤 기본 API 의존성을 설치한다.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

GPU Real-ESRGAN 검증이 필요할 때만 CUDA PyTorch와 `requirements-realesrgan.txt`, 공식 `vendor\Real-ESRGAN`을 추가 설치한다. 일반 API·데이터·화면 연동 개발에는 모델 설치가 필요하지 않다.

## 4. API 켜기와 끄기

### 켜기

```powershell
cd 'C:\Users\ktc system\나\3-1\경진대회\memory_restore'
.\scripts\run_local.cmd
```

실행 뒤 브라우저 또는 프론트엔드에서 다음 주소를 사용한다.

```text
http://127.0.0.1:5050
http://127.0.0.1:5050/api/v1/places
```

### 끄기

`run_local.cmd`를 실행한 터미널에서 `Ctrl+C`를 누른다. 백그라운드 프로세스나 외부 포트는 만들지 않는다.

### 정상 동작 확인

```powershell
Invoke-RestMethod http://127.0.0.1:5050/api/v1/places
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 5. 코드별 역할

| 위치 | 하는 일 | 수정하는 경우 |
| --- | --- | --- |
| `app.py` | Flask 앱, CORS, 장소·이미지 API | 새 API 경로를 추가할 때 |
| `data\places.json` | 역사 사진의 출처, 장소 정보, 매칭 신뢰도 | 공개 자료를 추가할 때 |
| `services\restoration.py` | 원본 보존형 출력과 복원 기록 | 결과물/기록 형식을 바꿀 때 |
| `services\model_selection.py` | 해상도에 따른 보수적 모델 선택 | 모델 선택 기준을 바꿀 때 |
| `services\realesrgan_adapter.py` | Flask 작업과 GPU 워커 연결 설정 | 업로드·작업 API를 연결할 때 |
| `scripts\realesrgan_worker.py` | 공식 Real-ESRGAN 일반 이미지 복원 실행 | 모델 실행 방식을 점검할 때 |
| `scripts\run_local.cmd` | Windows 로컬 Flask 실행 | 평소 로컬 개발 시작 |
| `scripts\server_control.py` | 나중에 Linux 서버에서만 쓰는 로컬 바인딩 제어 | 승인된 서버 배포 시 |
| `tests\` | API와 복원 규칙 회귀 테스트 | 코드 변경 후 검증 |
| `docs\frontend_api_contract.md` | 프론트엔드 팀 전달용 요청·응답 계약 | 화면 연동 시 |
| `docs\restoration_api_v2.md` | 업로드·복원·결과조회 API 계약 | 사진 복원 화면 연동 시 |
| `docs\frontend_integration_guide.md` | 화면 팀의 상태·오류·결과 표시 연동 가이드 | 반응형 화면을 붙일 때 |
| `docs\ui_prototype_spec.md` | 시연 UI의 정보 구조·시각 토큰·공통 UI 이관 규칙 | 공통 UI로 교체할 때 |
| `examples\frontend_api_client.js` | 프레임워크 독립적인 `fetch` API 클라이언트 | 화면 코드에서 바로 가져갈 때 |
| `benchmarks\` | 내부 정량 평가 CSV/JSON | 모델 비교 실험 시, UI 노출 금지 |

전체 폴더 설명은 `docs\project_structure.md`, 서버 이관 절차는 `docs\server_deployment.md`에 별도로 정리돼 있다.

## 6. 나중에 서버로 옮길 때

1. `memory_restore`와 `photos`를 동일한 상위 폴더의 형제 구조로 복사한다.
2. `bash scripts/setup_gpu_runtime.sh`로 프로젝트 전용 `.venv`를 만든다.
3. `scripts/realesrgan_worker.py`로 공개 사진 한 장을 먼저 검증한다.
4. 관리자 승인 전에는 `127.0.0.1` 바인딩을 유지한다.
5. 외부 팀 연동이 필요하면 임의 포트 공개 대신 학교가 허용한 리버스 프록시 또는 배포 경로를 확인한다.
