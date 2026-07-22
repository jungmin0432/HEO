# 학교 Jupyter 서버 배포 준비

## 필요한 정보

1. Jupyter 접속 URL과 사용 가능한 터미널 또는 노트북 실행 방식
2. Python 버전
3. GPU가 있다면 `nvidia-smi` 출력
4. 외부에서 Flask 포트를 직접 열 수 있는지, 또는 Jupyter Server Proxy를 써야 하는지

## 권장 구조

```text
반응형 프론트엔드 -> Flask API -> Real-ESRGAN 실행기 -> GPU
                    └-> 기준선(Pillow) 처리
```

프론트엔드는 GPU·PyTorch에 직접 접근하지 않는다. 모델 가중치는 서버의 `models/`처럼 별도 경로에 두고 Git·공유 드라이브에 올리지 않는다.

## 설치 순서

Jupyter의 터미널 또는 노트북 셀에서 아래 순서로 진행한다.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install basicsr realesrgan
```

CUDA 버전이 다르면 PyTorch 설치 주소를 해당 환경에 맞춰 바꾼다. GPU가 없으면 `cu121` 명령을 사용하지 않고 CPU용 PyTorch를 설치하되, 시연 지연을 피하려면 Real-ESRGAN은 GPU 서버에서 실행하는 것을 우선한다.

## 배포 전 확인 항목

- `nvidia-smi`로 GPU가 보이는가
- 작은 공개 사진 한 장을 2배 확대했을 때 결과 파일이 생성되는가
- 모델명, 확대 배율, 타일 크기, 생성 시각이 복원기록에 남는가
- 원본 해시가 처리 전후 그대로인가
- 외부 프론트엔드에서 `/api/v1/places`와 복원 결과 URL에 접근 가능한가
