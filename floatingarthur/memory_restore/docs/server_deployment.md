# School GPU Server Deployment

The school GPU server uses the same sibling-folder layout as the local project:

```text
/home/data/
  memory_restore/
  photos/
```

`memory_restore` must not be placed inside `/home/data/aicoss-0713`. The Flask application resolves public reference images from its sibling `../photos` folder.

## First-Time Setup

```bash
cd /home/data/memory_restore
bash scripts/setup_gpu_runtime.sh
```

The script creates `/home/data/memory_restore/.venv`, reuses CUDA PyTorch from the `bootcamp` environment, and installs the headless OpenCV runtime needed by the Jupyter server.

## Verify the Model

```bash
cd /home/data/memory_restore
.venv/bin/python scripts/realesrgan_worker.py \
  --input ../photos/history_photo/euljiro_line2_opening_1983/111937895/2015112201243932767.JPG \
  --output outputs/server_check.jpg \
  --model RealESRGAN_x2plus --outscale 2 --tile 256
```

## Start the API

```bash
cd /home/data/memory_restore
.venv/bin/python scripts/server_control.py start
```

## Stop or Check the API

```bash
cd /home/data/memory_restore
.venv/bin/python scripts/server_control.py status
.venv/bin/python scripts/server_control.py stop
```

The controller writes the process ID to `runtime/flask.pid` and logs to `runtime/flask.log`. It binds to `127.0.0.1:5050` only, so it does not allow external access. Do not restart the shared Jupyter server or change this bind address without the administrator's approval.
