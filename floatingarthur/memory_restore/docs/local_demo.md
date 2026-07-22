# Local API Demo

The Flask project is intentionally API-only so it can be combined with the separate responsive frontend.

## Start

```powershell
cd "C:\Users\ktc system\나\3-1\경진대회\memory_restore"
cmd /c .\scripts\run_local.cmd
```

If the PowerShell execution policy allows scripts, `./scripts/run_local.ps1` also accepts an optional `-Port` value.

The default local address is `http://127.0.0.1:5050`.

## Check

```powershell
Invoke-RestMethod http://127.0.0.1:5050/api/v1/places
Invoke-RestMethod http://127.0.0.1:5050/api/v1/restorations
```

`/api/v1/places` returns historical source, attribution, and match status. `/api/v1/restorations` returns restoration records. Evaluation metrics remain only in `benchmarks/` and are not part of these APIs.

## Frontend Integration

During development, the API sends permissive CORS headers. The frontend can use the local base URL above, then replace only its API base URL when the GPU worker server is ready.
