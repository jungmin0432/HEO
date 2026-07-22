# Frontend Integration Guide

## Local Connection

Start the API on the same computer as the frontend and use `http://127.0.0.1:5050` as the base URL. Do not use a LAN address, public IP, tunnel, or external server address.

```js
import { createRestorationApi, toResultViewModel } from "../memory_restore/examples/frontend_api_client.js";

const api = createRestorationApi();
```

## Initial Screen Data

1. Call `api.health()` once. `ai_mode: "enabled"` means the local process was started with the GPU worker enabled; `baseline_only` means an upload still works but returns comparison images without an AI result.
2. Call `api.listPlaces()` for the historical-place cards and their source/matching labels.
3. Keep `matching_status`, `matching_note`, and archive attribution visible whenever a place card or reference asset appears.

## Upload Flow

```js
const record = await api.createRestoration({
  file: selectedFile,
  placeId: selectedPlaceId,
  useAi: true,
  sourceAttribution: "Local prototype upload",
});

const result = toResultViewModel(record, api.resolveAsset);
```

The request is synchronous for the competition demo. Disable duplicate submission while the request is pending, retain the selected preview locally, and move to the result state only after the response arrives. Do not invent a percentage progress value; the backend deliberately does not expose model timing or benchmark data.

## Result-State Rules

| `ai_status` | Frontend behavior |
| --- | --- |
| `completed` | Show original, conservative, expressive, and AI result comparison. Label the AI image as a generated restoration and retain the warning text. |
| `unavailable` | Show original, conservative, and expressive comparison. Explain that this local runtime did not enable the GPU worker; do not show a fake AI result. |
| `preserve_priority` | Show original and baseline comparison first. Explain that the high-resolution input was preserved rather than upscaled. |
| `not_requested` | Show original and baseline comparison only. |

Always use the `assets` URLs returned by the response. They are relative API paths; call `api.resolveAsset()` before placing them in an image element when the frontend runs on a different local port.

Show a download control for every available `downloads[variantId]` URL. Also render `historical_context` beside the comparison when present, then render each `explanations` item as **change / basis / limit**. The rationale explains processing choices; it must never claim that generated detail proves the original historical scene.

## Error Rules

| HTTP status | Meaning | UI response |
| --- | --- | --- |
| `400` | Missing image, unsupported format, invalid image, or unknown place ID | Keep the selection screen and show a concise validation message. |
| `413` | File exceeds 15 MB | Ask for a smaller JPG, PNG, or WebP file. |
| `500` | Local processing failure | Preserve the selected preview, show a retry control, and do not claim a result was created. |

## Privacy and Trust Constraints

- Do not render PSNR, SSIM, processing time, model benchmarks, face enhancement, or place-matching guesses.
- Do not call the API from a public deployment. This prototype is local-only.
- `REFERENCE` and `NEARBY` assets must not be described as an exact past-and-present viewpoint match.
- Keep the original output and warnings available beside any AI result.
