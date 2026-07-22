"""Patch the one BasicSR import that changed in recent torchvision releases."""

from __future__ import annotations

import site
from pathlib import Path


OLD_IMPORT = "from torchvision.transforms.functional_tensor import rgb_to_grayscale"
NEW_IMPORT = "from torchvision.transforms.functional import rgb_to_grayscale"


def main() -> None:
    candidates = [
        Path(package_root) / "basicsr" / "data" / "degradations.py"
        for package_root in site.getsitepackages()
    ]
    target = next((candidate for candidate in candidates if candidate.is_file()), None)
    if target is None:
        raise RuntimeError("BasicSR is not installed in this Python environment.")

    source = target.read_text(encoding="utf-8")
    if NEW_IMPORT in source:
        print(f"BasicSR is already compatible: {target}")
        return
    if OLD_IMPORT not in source:
        raise RuntimeError(f"Unexpected BasicSR import layout: {target}")

    target.write_text(source.replace(OLD_IMPORT, NEW_IMPORT), encoding="utf-8")
    print(f"Patched BasicSR torchvision compatibility: {target}")


if __name__ == "__main__":
    main()
