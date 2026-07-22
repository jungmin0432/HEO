# GPU Runtime

This project uses the official Real-ESRGAN repository in `vendor/Real-ESRGAN` for general-image restoration. It does not install or call GFPGAN, and the worker does not expose a face-enhancement option.

## Required Runtime

Use the server's `bootcamp` Python environment with CUDA available. The project creates its own `.venv` with system packages enabled, so it reuses the server GPU PyTorch without modifying the shared `bootcamp` environment. The project was verified locally with a CUDA-enabled RTX 3080 and on the school server with an NVIDIA RTX A6000 detected by the `bootcamp` interpreter.

## Install

```bash
cd /home/data/aicoss-0713/memory_restore
bash scripts/setup_gpu_runtime.sh
```

`setup_gpu_runtime.sh` applies the documented BasicSR / torchvision import compatibility update automatically. This changes neither model weights nor inference behavior.

The runtime uses `opencv-python-headless`, which avoids a desktop OpenGL dependency on the Jupyter GPU server.

## Verify GPU

```bash
.venv/bin/python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

## Run a Worker Check

```bash
.venv/bin/python scripts/realesrgan_worker.py \
  --input ../photos/history_photo/euljiro_line2_opening_1983/111937895/2015112201243932767.JPG \
  --output outputs/server_check.jpg \
  --model RealESRGAN_x2plus --outscale 2 --tile 256
```

The official inference script downloads the selected pretrained weight to `vendor/Real-ESRGAN/weights/` on first use. Keep that directory out of version control and include its model name, output scale, and tile size in the restoration record.
