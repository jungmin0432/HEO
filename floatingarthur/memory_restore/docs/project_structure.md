# Project Structure

## Top-Level Server Layout

```text
/home/data/
  memory_restore/     # Flask API and restoration logic
  photos/             # public historical/current reference photos
```

The sibling layout is required. `app.py` reads `../photos`, so moving `photos` inside `memory_restore` or `memory_restore` inside `aicoss-0713` breaks the default path contract.

## `memory_restore` Layout

```text
memory_restore/
  app.py
  data/
  services/
  scripts/
  docs/
  tests/
  benchmarks/
  vendor/Real-ESRGAN/
  outputs/            # generated locally; not source-controlled
  runtime/            # Flask PID and logs; generated on the server
  .venv/              # project-only Python environment; generated on the server
```

## What Each Part Does

| Location | Role | Edit When |
| --- | --- | --- |
| `app.py` | Flask app factory, CORS, read-only place and asset APIs | Adding or changing API routes |
| `data/places.json` | Curated place metadata, source links, matching confidence | Adding a public historical/current place reference |
| `services/restoration.py` | Non-destructive baseline variants and restoration-record structure | Changing provenance or output-record behavior |
| `services/model_selection.py` | Resolution-aware model plan and conservative processing policy | Changing input-resolution policy |
| `services/realesrgan_adapter.py` | Optional command configuration for the Real-ESRGAN worker | Connecting the API job layer to GPU inference |
| `services/benchmark.py` | Internal quality metrics and controlled comparison support | Running internal model evaluation only |
| `scripts/realesrgan_worker.py` | Calls official general-image Real-ESRGAN with allowed models only | GPU restoration execution; no face enhancement |
| `scripts/setup_gpu_runtime.sh` | Creates server `.venv` and installs GPU inference dependencies | First server setup or environment repair |
| `scripts/patch_basicsr_compat.py` | Applies the BasicSR / torchvision import compatibility fix | Called automatically by GPU setup |
| `scripts/server_control.py` | Starts, stops, and checks the local-only Flask process | Operating the server |
| `scripts/run_local.cmd` | Starts the local Windows Flask API | Local development on Windows |
| `docs/` | API contract, data model, runtime and deployment instructions | Handing off or integrating with the frontend |
| `tests/` | Focused API, output-record, resolution-policy tests | Before sharing code changes |
| `benchmarks/` | Internal CSV/JSON evidence for model comparison | Offline evaluation; never expose in demo UI |
| `vendor/Real-ESRGAN/` | Checked-in official inference source | Do not edit unless updating the upstream dependency |

## Runtime Files You Do Not Edit Manually

| Location | Reason |
| --- | --- |
| `.venv/` | Recreated with `bash scripts/setup_gpu_runtime.sh` |
| `runtime/flask.pid` | Written and removed by `server_control.py` |
| `runtime/flask.log` | Server diagnostics; read it when startup fails |
| `outputs/` | Generated restorations; keep original input and JSON record together |
| `vendor/Real-ESRGAN/weights/` | Official pretrained weights downloaded at first inference |

## Day-to-Day Commands

```bash
cd /home/data/memory_restore
.venv/bin/python scripts/server_control.py start
.venv/bin/python scripts/server_control.py status
.venv/bin/python scripts/server_control.py stop
```
