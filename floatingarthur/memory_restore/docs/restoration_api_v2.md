# Restoration API v2

The local Flask prototype accepts a user image, keeps a source-preserving record, and returns URLs for comparison results. It listens on `127.0.0.1:5050` only.

## Create a Restoration

`POST /api/v1/restorations` with `multipart/form-data`.

| Field | Required | Meaning |
| --- | --- | --- |
| `source_mode` | no | `archive` for the selected public historical record; `upload` for a local user image (default) |
| `photo` | with `upload` | JPG, PNG, or WebP image, maximum 15 MB |
| `place_id` | with `archive`; optional with `upload` | One of the IDs returned by `GET /api/v1/places` |
| `use_ai` | no | `true` by default; set `false` for baseline comparison only |
| `source_attribution` | no | Local-demo source note stored in the record |

The response is synchronous for the demo. It includes `record_id`, the chosen resolution policy, `ai_status`, warning text, assets, downloads, explanations, and selected `historical_context`. `ai_status` is `completed`, `not_requested`, `unavailable`, or `preserve_priority`.

PNG input is supported end to end. The preserved original and, when AI restoration runs, the AI output retain the input extension so their browser media type remains correct.

## Read a Result

| Request | Result |
| --- | --- |
| `GET /api/v1/restorations/{record_id}` | Full record with asset URLs |
| `GET /api/v1/restorations/{record_id}/assets/{variant_id}` | One original, baseline, or AI image |
| `GET /api/v1/restorations/{record_id}/downloads/{variant_id}` | Attachment download with a stable filename |
| `GET /api/v1/restorations/{record_id}/explanation` | Variant-level change basis, method, and limitation text |
| `GET /api/v1/restorations` | Existing restoration records |

## Enable Local GPU Inference

The API does not silently enable a model. In a CUDA-ready local virtual environment, start Flask with:

```powershell
$env:ENABLE_LOCAL_REALESRGAN = '1'
.\scripts\run_local.cmd
```

Without this environment variable, uploads still create preserved and baseline comparison results and return `ai_status: "unavailable"` when AI was requested. The API does not expose benchmark metrics, face enhancement, colorization, or place matching.
