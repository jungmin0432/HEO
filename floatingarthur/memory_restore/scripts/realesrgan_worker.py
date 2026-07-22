from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "vendor" / "Real-ESRGAN"
INFERENCE_SCRIPT = VENDOR_ROOT / "inference_realesrgan.py"
ALLOWED_MODELS = {"RealESRGAN_x2plus", "RealESRGAN_x4plus"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the official Real-ESRGAN general-image inference script.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", choices=sorted(ALLOWED_MODELS), required=True)
    parser.add_argument("--outscale", type=int, choices=(2, 3, 4), required=True)
    parser.add_argument("--tile", type=int, default=256)
    parser.add_argument("--gpu-id", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input.is_file():
        raise FileNotFoundError(args.input)
    if not INFERENCE_SCRIPT.is_file():
        raise RuntimeError(f"Official Real-ESRGAN source is missing: {INFERENCE_SCRIPT}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="realesrgan-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        # OpenCV in the upstream Windows script cannot reliably open Unicode paths.
        worker_input = temporary_root / f"input{args.input.suffix.lower()}"
        shutil.copyfile(args.input, worker_input)
        command = [
            sys.executable,
            str(INFERENCE_SCRIPT),
            "-n",
            args.model,
            "-i",
            str(worker_input),
            "-o",
            str(temporary_root),
            "--outscale",
            str(args.outscale),
            "-t",
            str(args.tile),
            "-g",
            str(args.gpu_id),
            "--suffix",
            "restored",
        ]
        completed = subprocess.run(
            command,
            cwd=VENDOR_ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "Official Real-ESRGAN inference failed")

        generated = temporary_root / f"input_restored{args.input.suffix.lower()}"
        if not generated.is_file():
            raise RuntimeError("Real-ESRGAN finished without producing an output file")
        shutil.copyfile(generated, args.output)

    print(
        json.dumps(
            {
                "model": args.model,
                "outscale": args.outscale,
                "tile": args.tile,
                "gpu_id": args.gpu_id,
                "face_enhancement": False,
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
