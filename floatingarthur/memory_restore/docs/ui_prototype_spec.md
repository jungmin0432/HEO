# UI Prototype Specification

## Scope

`ui_prototype/` is a local, API-connected service reference. It is not the common frontend implementation. The common UI may replace its technology, component library, and page structure while retaining the information hierarchy, trust rules, and API state handling below.

## Visual Direction

The UI treats the underground arcade as a sequence of connected time zones rather than a generic AI dashboard.

| Token | Value | Purpose |
| --- | --- | --- |
| Ink | `#11221f` | Main text and structural contrast |
| Forest | `#0e4134` | Main route, title, selected record |
| Teal | `#13818a` | Restoration and active system state |
| Vermilion | `#c33b24` | Making/printing zone and warning accent |
| Cobalt | `#274f92` | DDP connection zone |
| Signal | `#f1b63c` | Historical image and selected-year accent |

The design uses a pale neutral field, ink-like borders, compact 6px radii, real archival imagery, and a four-stop route line. It avoids decorative gradients, floating cards, and AI-dashboard visual tropes.

## Information Architecture

1. **Intro / selected record**: introduces the time-based journey and shows the selected public historical image with attribution.
2. **Four-zone route**: `을지로입구 → 을지로3가 → 을지로4가 → DDP 연결부`. The route is navigation and context, not a progress claim.
3. **Record selection**: public place cards retain year, matching status, and matching note.
4. **Restore workspace**: local image selection, AI comparison opt-in, local preview, start action.
5. **Result comparison**: preserved original, conservative baseline, expressive baseline, optional AI output, warnings.

## Responsive Behavior

| Viewport | Layout |
| --- | --- |
| Desktop | Intro and image in two columns; work area in two columns; four result images in one row. |
| Mobile | Intro stacks; route keeps a horizontally scrollable fixed-width line; place cards and workspace stack; result images become a two-column grid. |

## Component and API Mapping

| UI region | Source | Required data |
| --- | --- | --- |
| API indicator | `GET /api/v1/health` | `ai_mode`, `bind_scope` |
| Historical record rail | `GET /api/v1/places` | title, year, matching status/note, archive attribution |
| Historical image | `GET /assets/history/{place_id}` | selected `place_id` |
| Upload action | `POST /api/v1/restorations` | `photo`, optional `place_id`, `use_ai` |
| Result grid | upload response or `GET /api/v1/restorations/{record_id}` | `assets`, `ai_status`, warnings, plan |

## Required Result States

- `completed`: show all available comparison images and mark AI output distinctly.
- `unavailable`: do not imitate an AI result; retain original and baseline images.
- `preserve_priority`: explain that high-resolution input did not need AI enlargement.
- `not_requested`: show baseline images only.
- request failure: preserve the pre-upload preview and allow retry without inventing a result state.

## Common UI Handoff Rules

- Keep `/prototype` only as a local reference; do not import its CSS into the common frontend.
- Reuse `examples/frontend_api_client.js` or reimplement its request behavior in the common UI stack.
- Do not remove archive attribution, matching constraints, original output, or warning copy from the result experience.
- Keep the API base local (`127.0.0.1`) until a separately approved deployment path exists.
