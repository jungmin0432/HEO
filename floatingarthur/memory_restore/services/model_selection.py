from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class InputProfile:
    width: int
    height: int
    megapixels: float


@dataclass(frozen=True)
class RestorationPlan:
    plan_id: str
    model_name: str | None
    outscale: int
    label: str
    reason: str
    requires_human_review: bool

    def to_dict(self) -> dict:
        return asdict(self)


def inspect_resolution(image_path: Path) -> InputProfile:
    with Image.open(image_path) as image:
        width, height = image.size
    return InputProfile(width=width, height=height, megapixels=round(width * height / 1_000_000, 3))


def select_restoration_plan(profile: InputProfile) -> RestorationPlan:
    """Choose the least aggressive method that can plausibly improve the input."""
    if profile.megapixels < 0.5:
        return RestorationPlan(
            plan_id="low-resolution-x4",
            model_name="RealESRGAN_x4plus",
            outscale=2,
            label="저해상도 AI 복원 후보",
            reason="0.5MP 미만 입력은 강한 초해상도 후보와 기준선을 비교한다.",
            requires_human_review=True,
        )
    if profile.megapixels < 2.0:
        return RestorationPlan(
            plan_id="medium-resolution-x2",
            model_name="RealESRGAN_x2plus",
            outscale=2,
            label="중간 해상도 AI 복원 후보",
            reason="0.5~2.0MP 입력은 과도한 확대보다 x2 모델을 우선 비교한다.",
            requires_human_review=True,
        )
    return RestorationPlan(
        plan_id="high-resolution-preserve",
        model_name=None,
        outscale=1,
        label="고해상도 보존형 우선",
        reason="2.0MP 이상 입력은 AI 확대보다 원본 보존·보수형 보정을 먼저 제시한다.",
        requires_human_review=False,
    )
