# 지하상가 경로 추천 (담당 파트)

"서울 아랫길 600년" 웹사이트 중 **지하상가 QR 경로 추천** 기능만 독립적으로 실행 가능하게 구성한 폴더입니다.

## 실행 방법

```bash
cd backend
pip install -r requirements.txt
python app.py
```

기본 주소: `http://127.0.0.1:5011/?gate=E4-01`
(포트를 바꾸려면 `PORT=5050 python app.py`처럼 환경변수를 지정)

QR 게이트 코드: `E1-01`, `E3-01`, `E3-02`, `E4-01`, `E4-02`, `DDP-01`

## 구조

| 파일 | 역할 |
|---|---|
| `backend/app.py` | Flask API (`/api/ai/routes/recommend` 등) + 프론트 서빙 |
| `backend/route_engine.py` | 영업시간·도보시간 필터 + Dijkstra 기반 코스 계산 (핵심 로직) |
| `backend/ai_interpreter.py` | 자유 문장 → 조건(JSON) 해석 (OpenAI 있으면 사용, 없으면 규칙 기반 fallback) |
| `backend/route_database.py`, `build_route_database.py` | 점포 DB 조회/구축용 |
| `backend/data/euljiro_route_20260722_project.db` | 실제 점포 데이터베이스 (공식 점포 161개 포함). `backend/data/euljiro_underground_directory_hours.csv`가 원본 소스이며, `python build_route_database.py`로 재생성 가능 |
| `backend/web/index.html` | 새로 디자인한 모바일 프론트엔드 (단일 파일, 외부 빌드 불필요) |
| `backend/web/photobooth.html` | 서울 시간네컷 — 브랜드 프레임을 씌운 4컷 촬영 페이지 (`/photobooth`) |

## 디자인 방향

제안서의 "서울 아랫길 600년" 콘셉트(1394 도성 → 1984 지하도시 → 오늘의 DDP로 이어지는 4개 구역)를 반영했습니다.

- **톤**: 네이비(역사·야경) + 골드(오래된 것의 가치) + 크림(종이·한지)
- **구역별 색**: 을지로입구(호박색) · 을지로3가(테라코타) · 을지로4가(청록) · DDP(인디고) — 타임라인에서 정류장 아이콘 테두리 색으로 구분
- **결과 화면**: "탑승권" 형태의 티켓 카드(펀칭 구멍·점선 구분선)로 총 소요시간·실제 체험시간·도보거리를 보여주고, 그 아래 세로 타임라인으로 정류장을 나열
- 유니코드 기호 대신 인라인 SVG 아이콘 세트 사용, 로딩 스켈레톤·전환 애니메이션 추가
- 모바일 우선(최대폭 430px), 안전영역(`env(safe-area-inset-*)`) 대응, 하단 고정 CTA

## 테스트

```bash
cd backend
python -m unittest test_route_engine -v
```
