#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTCAMP_PYTHON="${BOOTCAMP_PYTHON:-/opt/miniconda3/envs/bootcamp/bin/python}"
VENV_DIR="${PROJECT_ROOT}/.venv"

if [[ ! -x "${BOOTCAMP_PYTHON}" ]]; then
  echo "bootcamp Python was not found: ${BOOTCAMP_PYTHON}" >&2
  exit 1
fi

cd "${PROJECT_ROOT}"
"${BOOTCAMP_PYTHON}" -m venv --system-site-packages "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r requirements.txt
# BasicSR 1.4.2 is published as a source package. Reuse this venv's build
# tools instead of requesting a second isolated build environment on Jupyter.
"${VENV_DIR}/bin/python" -m pip install --no-build-isolation basicsr==1.4.2
"${VENV_DIR}/bin/python" -m pip uninstall -y opencv-python
"${VENV_DIR}/bin/python" -m pip install --upgrade opencv-python-headless
"${VENV_DIR}/bin/python" -m pip install --no-deps -e vendor/Real-ESRGAN
"${VENV_DIR}/bin/python" scripts/patch_basicsr_compat.py
"${VENV_DIR}/bin/python" -c "import torch; assert torch.cuda.is_available(), 'GPU is unavailable'; print(torch.cuda.get_device_name(0))"

echo "GPU runtime is ready: ${VENV_DIR}"
