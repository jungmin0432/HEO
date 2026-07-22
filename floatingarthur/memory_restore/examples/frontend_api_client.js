export class RestorationApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = "RestorationApiError";
    this.status = status;
    this.details = details;
  }
}

export function createRestorationApi(baseUrl = "http://127.0.0.1:5050") {
  const root = baseUrl.replace(/\/$/, "");

  async function request(path, options = {}) {
    const response = await fetch(`${root}${path}`, options);
    const contentType = response.headers.get("content-type") ?? "";
    const body = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok) {
      throw new RestorationApiError(body?.error ?? "API request failed", response.status, body);
    }
    return body;
  }

  function resolveAsset(path) {
    return new URL(path, `${root}/`).toString();
  }

  return {
    health: () => request("/api/v1/health"),
    listPlaces: () => request("/api/v1/places"),
    getPlace: (placeId) => request(`/api/v1/places/${encodeURIComponent(placeId)}`),
    getRestoration: (recordId) => request(`/api/v1/restorations/${encodeURIComponent(recordId)}`),
    resolveAsset,
    async createRestoration({ file, placeId = null, useAi = true, sourceAttribution = null }) {
      const form = new FormData();
      form.append("photo", file);
      form.append("use_ai", String(useAi));
      if (placeId) form.append("place_id", placeId);
      if (sourceAttribution) form.append("source_attribution", sourceAttribution);
      return request("/api/v1/restorations", { method: "POST", body: form });
    },
  };
}

export function toResultViewModel(record, resolveAsset) {
  const hasAiResult = Boolean(record.assets?.ai_restored);
  return {
    recordId: record.record_id,
    originalUrl: resolveAsset(record.assets.preserve),
    conservativeUrl: resolveAsset(record.assets.conservative),
    expressiveUrl: resolveAsset(record.assets.expressive),
    aiUrl: hasAiResult ? resolveAsset(record.assets.ai_restored) : null,
    aiStatus: record.ai_status,
    showAiComparison: hasAiResult,
    showPreserveFirstMessage: record.ai_status === "preserve_priority",
    showAiUnavailableMessage: record.ai_status === "unavailable",
    warnings: record.warnings ?? [],
    matchingStatus: record.place_id ? "selected_place" : "not_linked",
  };
}
