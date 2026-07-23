"""사진 복원 미리보기 — 무료 AI 미리보기 / 유료 점포 고해상 제작을 분리(제안서 3.4).

여기서는 '무료 미리보기' 계층을 고전적 영상처리로 구현한다:
노이즈 제거 → 자동 대비 → 언샤프 → 2배 업스케일.
생성형 합성은 하지 않는다(존재하지 않은 얼굴/역사를 지어내지 않음).
고해상 복원·색보정은 점포가 승인 후 처리 — 제안서의 무료/유료 경계 그대로.

프로덕션 경로는 Real-ESRGAN(딥러닝 초해상). Windows 로컬에서 torch 가중치가 무거워
데모/미리보기는 Pillow 기반 고전 처리로 두고, 인터페이스는 동일하게 유지한다.
"""
from __future__ import annotations

import base64
import io

try:
    from PIL import Image, ImageFilter, ImageOps
    HAVE_PIL = True
except Exception:  # Pillow 미설치 시에도 서버는 뜨고, 엔드포인트만 501 반환
    HAVE_PIL = False


def available() -> bool:
    return HAVE_PIL


def restore_preview(image_bytes: bytes) -> dict:
    """원본 바이트 → {before, after}(PNG base64) + 메타. 미리보기 표식 포함."""
    if not HAVE_PIL:
        raise RuntimeError("Pillow 미설치 — pip install pillow 후 사용 가능")

    src = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = src.size

    # 1) 노이즈 제거  2) 자동 대비  3) 언샤프  4) 2배 업스케일
    work = src.filter(ImageFilter.MedianFilter(size=3))
    work = ImageOps.autocontrast(work, cutoff=1)
    work = work.filter(ImageFilter.UnsharpMask(radius=2, percent=140, threshold=2))
    restored = work.resize((w * 2, h * 2), Image.LANCZOS)

    def to_b64(img: Image.Image) -> str:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    return {
        "before": to_b64(src),
        "after": to_b64(restored),
        "meta": {
            "src_size": [w, h],
            "out_size": [w * 2, h * 2],
            "scale": 2,
            "ai_preview": True,            # AI 복원 표식(합성 아님)
            "note": "무료 미리보기 · 고해상 복원과 가격·납기는 점포가 승인",
            "pipeline": ["denoise", "autocontrast", "unsharp", "upscale x2"],
        },
    }
