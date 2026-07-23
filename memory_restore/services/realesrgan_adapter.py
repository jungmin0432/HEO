from __future__ import annotations

import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class AIBackendUnavailable(RuntimeError):
    """Raised when the server has not been configured with an AI runner."""


@dataclass(frozen=True)
class RealESRGANSettings:
    command_template: str
    model_name: str
    tile: int
    use_local_worker: bool

    @classmethod
    def from_environment(cls) -> "RealESRGANSettings":
        return cls(
            command_template=os.getenv("REALESRGAN_COMMAND", "").strip(),
            model_name=os.getenv("REALESRGAN_MODEL", "RealESRGAN_x4plus"),
            tile=int(os.getenv("REALESRGAN_TILE", "256")),
            use_local_worker=os.getenv("ENABLE_LOCAL_REALESRGAN", "").strip() == "1",
        )


def run_realesrgan(
    input_path: Path,
    output_path: Path,
    outscale: int = 2,
    model_name: str | None = None,
) -> dict:
    """Invoke a server-provided Real-ESRGAN worker without exposing GPU details to the web UI."""
    settings = RealESRGANSettings.from_environment()
    if not settings.command_template and not settings.use_local_worker:
        raise AIBackendUnavailable(
            "REALESRGAN_COMMAND is not configured. Use the baseline backend or prepare the school server."
        )
    if outscale not in {2, 3, 4}:
        raise ValueError("outscale must be 2, 3, or 4")
    if not input_path.is_file():
        raise FileNotFoundError(input_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    selected_model = model_name or settings.model_name
    if settings.use_local_worker:
        worker = Path(__file__).resolve().parents[1] / "scripts" / "realesrgan_worker.py"
        command = [
            sys.executable,
            str(worker),
            "--input",
            str(input_path.resolve()),
            "--output",
            str(output_path.resolve()),
            "--model",
            selected_model,
            "--outscale",
            str(outscale),
            "--tile",
            str(settings.tile),
        ]
    else:
        command = shlex.split(
            settings.command_template.format(
                input=str(input_path.resolve()),
                output=str(output_path.resolve()),
                model=selected_model,
                outscale=outscale,
                tile=settings.tile,
            ),
            posix=os.name != "nt",
        )
    completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=300)
    if completed.returncode != 0:
        raise RuntimeError(f"Real-ESRGAN worker failed: {completed.stderr.strip()}")
    if not output_path.is_file():
        raise RuntimeError("Real-ESRGAN worker finished without producing an output file")

    return {
        "name": "Real-ESRGAN",
        "model": selected_model,
        "outscale": outscale,
        "tile": settings.tile,
        "generative_ai": True,
        "face_enhancement": False,
        "stdout": completed.stdout.strip(),
    }
