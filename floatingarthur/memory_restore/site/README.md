# UI Prototype

This folder is an isolated local-demo reference for the common frontend team. It is served only at `/prototype` by the Flask app and uses the public API through `fetch`.

It does not define a shared component system, routing convention, or deployment configuration. When the common UI replaces it, preserve these behaviors:

- place source and matching-status presentation;
- local file preview before upload;
- mobile `현재 장면 입력 → 후보 목록 → 후보 상세 → 복원` hierarchy;
- candidate evidence, archive source link, and visible matching limitations;
- explicit user selection before forwarding `matched_asset_id` to restoration;
- `ai_status`-specific result states;
- original-preserved comparison alongside every AI result;
- local-only API base URL.

For a standalone frontend dev server, open the prototype with `?apiBase=http://127.0.0.1:5050` and keep the Flask API running separately.

The API contract, frontend handoff, and mobile scenarios are documented in `../docs/location_matching_api.md`, `../docs/location_matching_frontend_guide.md`, and `../docs/location_matching_ui_scenarios.md`.
