const apiBase = new URLSearchParams(window.location.search).get("apiBase") || window.location.origin;
const api = (path, options = {}) => fetch(`${apiBase}${path}`, options).then(async (response) => {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || "요청을 처리하지 못했습니다.");
  return body;
});

const zones = [
  { id: "entrance", number: "1", title: "을지로입구", subtitle: "서울의 장면을 고르다", color: "#0e4134" },
  { id: "memory", number: "2", title: "을지로3가", subtitle: "기억을 읽고 복원하다", color: "#13818a" },
  { id: "maker", number: "3", title: "을지로4가", subtitle: "서울을 찍어내고 만들다", color: "#c33b24" },
  { id: "ddp", number: "4", title: "DDP 연결부", subtitle: "오늘의 서울을 펼치다", color: "#274f92" },
];

const state = {
  places: [], selectedPlace: null, selectedFile: null, previewUrl: null, sourceMode: "archive", selectedMatchCandidate: null,
};
const matchState = { file: null, previewUrl: null, candidates: [], selectedCandidate: null };
const elements = {
  apiStatus: document.querySelector("#api-status"),
  journeyStops: document.querySelector("#journey-stops"),
  placeRail: document.querySelector("#place-rail"),
  placeImage: document.querySelector("#place-image"),
  placeYear: document.querySelector("#place-year"),
  placeStatus: document.querySelector("#place-status"),
  placeAttribution: document.querySelector("#place-attribution"),
  fileInput: document.querySelector("#photo-input"),
  uploadPanel: document.querySelector(".upload-panel"),
  restoreHeading: document.querySelector("#restore-heading"),
  modeDescription: document.querySelector("#mode-description"),
  fileTitle: document.querySelector("#file-title"),
  previewFrame: document.querySelector("#preview-frame"),
  previewHeading: document.querySelector("#preview-heading"),
  restoreButton: document.querySelector("#restore-button"),
  aiToggle: document.querySelector("#ai-toggle"),
  uploadNote: document.querySelector("#upload-note"),
  resultSection: document.querySelector("#result-section"),
  resultSummary: document.querySelector("#result-summary"),
  resultGrid: document.querySelector("#result-grid"),
  historyConnection: document.querySelector("#history-connection"),
  explanationPanel: document.querySelector("#explanation-panel"),
  warningList: document.querySelector("#warning-list"),
};
const finder = {
  flow: document.querySelector("#finder-flow"),
  open: document.querySelector("#finder-open"),
  close: document.querySelector("#finder-close"),
  title: document.querySelector("#finder-flow-title"),
  step: document.querySelector("#finder-step"),
  inputScreen: document.querySelector("#finder-input-screen"),
  resultsScreen: document.querySelector("#finder-results-screen"),
  detailScreen: document.querySelector("#finder-detail-screen"),
  fileInput: document.querySelector("#match-photo-input"),
  fileTitle: document.querySelector("#match-file-title"),
  latitude: document.querySelector("#match-latitude"),
  longitude: document.querySelector("#match-longitude"),
  accuracy: document.querySelector("#match-accuracy"),
  landmark: document.querySelector("#match-landmark"),
  submit: document.querySelector("#finder-submit"),
  status: document.querySelector("#finder-status"),
  decision: document.querySelector("#finder-decision-note"),
  results: document.querySelector("#finder-results"),
  detail: document.querySelector("#finder-detail"),
  resultsBack: document.querySelector("#finder-results-back"),
  detailBack: document.querySelector("#finder-detail-back"),
};

function assetUrl(path) { return new URL(path, `${apiBase}/`).toString(); }

function renderZones(activeIndex = 0) {
  elements.journeyStops.innerHTML = zones.map((zone, index) => `
    <button class="journey-stop ${index === activeIndex ? "is-active" : ""}" type="button" data-index="${index}">
      <span class="stop-number" style="background:${zone.color}">${zone.number}</span>
      <strong>${zone.title}</strong><span>${zone.subtitle}</span>
    </button>`).join("");
  elements.journeyStops.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => {
    renderZones(Number(button.dataset.index));
    const place = state.places[Number(button.dataset.index) % state.places.length];
    if (place) selectPlace(place);
  }));
}

function renderPlaceRail() {
  elements.placeRail.innerHTML = state.places.map((place) => `
    <button class="place-card ${place.id === state.selectedPlace?.id ? "is-selected" : ""}" type="button" data-place-id="${place.id}">
      <span class="place-card-year">${place.year} · ${place.matching_status}</span>
      <span class="place-card-title">${place.title}</span>
      <span class="place-card-note">${place.matching_note}</span>
    </button>`).join("");
  elements.placeRail.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => selectPlace(state.places.find((place) => place.id === button.dataset.placeId)));
  });
}

function selectPlace(place) {
  state.selectedPlace = place;
  elements.placeImage.src = assetUrl(`/assets/history/${place.id}`);
  elements.placeImage.alt = place.title;
  elements.placeYear.textContent = place.year;
  elements.placeStatus.textContent = place.matching_status;
  elements.placeAttribution.textContent = place.archive.attribution;
  renderPlaceRail();
  updateSourceMode();
}

function updateSourceMode() {
  const archiveMode = state.sourceMode === "archive";
  document.querySelectorAll(".mode-tab").forEach((button) => button.classList.toggle("is-active", button.dataset.mode === state.sourceMode));
  elements.uploadPanel.classList.toggle("is-archive-mode", archiveMode);
  elements.restoreHeading.textContent = archiveMode ? "기록 사진을 다시 읽기" : "나의 사진을 기록과 이어보기";
  elements.modeDescription.textContent = archiveMode
    ? "선택한 장소의 서울기록원 사진을 원본 보존형으로 복원합니다."
    : "선택한 기록을 맥락으로 남기고, 나의 사진은 별도 원본 보존형 결과로 비교합니다.";
  elements.restoreButton.textContent = archiveMode ? "기록 사진 복원" : "나의 사진 복원";
  elements.restoreButton.disabled = archiveMode ? !state.selectedPlace : !state.selectedFile;
  if (archiveMode) {
    elements.previewHeading.textContent = state.selectedPlace ? `${state.selectedPlace.year} 기록 사진` : "기록을 선택하세요";
    elements.previewFrame.innerHTML = state.selectedPlace
      ? `<img src="${assetUrl(`/assets/history/${state.selectedPlace.id}`)}" alt="선택한 기록 사진 미리보기" />`
      : "<span>ARCHIVE</span>";
  }
}

function selectFile(file) {
  if (!file) return;
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.selectedFile = file;
  state.previewUrl = URL.createObjectURL(file);
  elements.fileTitle.textContent = file.name;
  elements.previewHeading.textContent = "선택한 나의 사진";
  elements.previewFrame.innerHTML = `<img src="${state.previewUrl}" alt="업로드 전 선택한 사진 미리보기" />`;
  elements.restoreButton.disabled = false;
  elements.uploadNote.textContent = `${Math.ceil(file.size / 1024)}KB · 원본과 결과를 나란히 비교할 수 있습니다.`;
}

function renderResults(record) {
  const labels = [
    ["preserve", "원본 보존"], ["conservative", "보수 보정"], ["expressive", "표현 보정"], ["ai_restored", "AI 복원"],
  ];
  const cards = labels.filter(([key]) => record.assets[key]).map(([key, label]) => `
    <figure class="result-card"><img src="${assetUrl(record.assets[key])}" alt="${label} 결과" />
    <figcaption><span>${label}</span><a href="${assetUrl(record.downloads[key])}">저장</a></figcaption></figure>`).join("");
  elements.resultGrid.innerHTML = cards;
  elements.resultSummary.textContent = record.ai_status === "completed"
    ? "AI 결과도 원본과 함께 비교합니다. 생성 결과가 역사적 사실을 추가로 증명하지는 않습니다."
    : record.ai_status === "preserve_priority"
      ? "고해상도 입력은 확대보다 원본 보존과 보수 보정을 우선합니다."
      : "현재 환경에서는 원본 보존형 비교 결과를 먼저 제공합니다.";
  elements.warningList.innerHTML = (record.warnings || []).map((warning) => `<p>${warning}</p>`).join("");
  const context = record.historical_context;
  elements.historyConnection.innerHTML = context ? `<img src="${assetUrl(context.asset_url)}" alt="${context.title}" />
    <div><p class="eyebrow">RECORD CONNECTION</p><h3>${context.title} · ${context.year}</h3>
    <p>${context.matching_note}</p><a href="${context.archive.source_url}" target="_blank" rel="noreferrer">기록원 출처 열기</a></div>` : "";
  elements.explanationPanel.innerHTML = `<h3>변경 근거</h3>${(record.explanations || []).map((item) => `
    <article class="explanation-item"><h4>${item.title}</h4>
    <p><strong>변경</strong> ${item.what_changed}</p>
    <p><strong>근거</strong> ${item.basis}</p>
    <p><strong>한계</strong> ${item.limit}</p></article>`).join("")}`;
  elements.resultSection.hidden = false;
  elements.resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function showFinderScreen(name) {
  const screens = {
    input: [finder.inputScreen, "기록 찾기", "1 / 3"],
    results: [finder.resultsScreen, "후보 기록", "2 / 3"],
    detail: [finder.detailScreen, "기록 상세", "3 / 3"],
  };
  const [activeScreen, title, step] = screens[name];
  [finder.inputScreen, finder.resultsScreen, finder.detailScreen].forEach((screen) => {
    const isActive = screen === activeScreen;
    screen.hidden = !isActive;
    screen.classList.toggle("is-active", isActive);
  });
  finder.title.textContent = title;
  finder.step.textContent = step;
  finder.flow.scrollTo({ top: 0, behavior: "auto" });
}

function openFinder() {
  finder.flow.hidden = false;
  document.body.style.overflow = "hidden";
  showFinderScreen("input");
}

function closeFinder() {
  finder.flow.hidden = true;
  document.body.style.overflow = "";
}

function selectMatchFile(file) {
  if (!file) return;
  if (matchState.previewUrl) URL.revokeObjectURL(matchState.previewUrl);
  matchState.file = file;
  matchState.previewUrl = URL.createObjectURL(file);
  finder.fileTitle.textContent = file.name;
  finder.submit.disabled = false;
  finder.status.textContent = `${Math.ceil(file.size / 1024)}KB 사진을 선택했습니다.`;
}

function scoreLabel(candidate) {
  const score = Math.round((candidate.retrieval_score || 0) * 100);
  return `${score}점 후보 적합도`;
}

function candidateCard(candidate, index) {
  return `<button class="candidate-card" type="button" data-candidate-index="${index}">
    <img src="${assetUrl(candidate.asset_url)}" alt="${candidate.title}" />
    <span>
      <span class="candidate-card__meta"><span>${candidate.year} · ${candidate.series}</span><span class="candidate-card__score">${scoreLabel(candidate)}</span></span>
      <h3>${candidate.title}</h3>
      <p>${candidate.short_reason}</p>
    </span>
  </button>`;
}

function renderMatchResults(payload) {
  matchState.candidates = payload.candidates || [];
  finder.decision.textContent = payload.decision_note || "사진과 입력 단서를 바탕으로 기록 후보를 정렬했습니다.";
  if (!matchState.candidates.length) {
    finder.results.innerHTML = "<p class=\"candidate-limit\">지금 입력만으로는 출처가 확인된 후보를 조심스럽게 제시하기 어렵습니다. GPS 또는 주변 장소를 보완해 다시 찾아보세요.</p>";
  } else {
    finder.results.innerHTML = matchState.candidates.map(candidateCard).join("");
    finder.results.querySelectorAll("[data-candidate-index]").forEach((button) => {
      button.addEventListener("click", () => showCandidateDetail(matchState.candidates[Number(button.dataset.candidateIndex)]));
    });
  }
  showFinderScreen("results");
}

function showCandidateDetail(candidate) {
  if (!candidate) return;
  matchState.selectedCandidate = candidate;
  const evidence = (candidate.evidence || []).map((item) => `
    <article><h4>${item.label}</h4><p>${item.description}</p></article>`).join("");
  const limitations = (candidate.limitations || []).map((item) => `<li>${item}</li>`).join("");
  finder.detail.innerHTML = `<section class="candidate-detail">
    <img class="candidate-detail__image" src="${assetUrl(candidate.asset_url)}" alt="${candidate.title}" />
    <p class="candidate-detail__meta"><span>${candidate.year}</span><span>${candidate.series}</span></p>
    <h2 class="candidate-detail__title">${candidate.title}</h2>
    <p>${candidate.description}</p>
    <p class="candidate-detail__source"><a href="${candidate.archive.source_url}" target="_blank" rel="noreferrer">${candidate.archive.attribution}</a></p>
    <section class="candidate-evidence"><h3>후보로 제시한 이유</h3>${evidence}</section>
    <div class="candidate-limit"><strong>판단 한계</strong><ul>${limitations}</ul></div>
    <button class="primary-action candidate-use" id="candidate-use" type="button">이 기록과 내 사진 이어보기</button>
  </section>`;
  document.querySelector("#candidate-use").addEventListener("click", useCandidateForRestoration);
  showFinderScreen("detail");
}

function useCandidateForRestoration() {
  if (!matchState.selectedCandidate || !matchState.file) return;
  state.selectedMatchCandidate = matchState.selectedCandidate;
  state.sourceMode = "upload";
  updateSourceMode();
  selectFile(matchState.file);
  elements.uploadNote.textContent = `선택한 기록: ${matchState.selectedCandidate.title}. 복원 결과에 기록 연결과 판단 한계를 함께 남깁니다.`;
  closeFinder();
  document.querySelector("#record-section").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function findHistoricalCandidates() {
  if (!matchState.file) return;
  const form = new FormData();
  form.append("photo", matchState.file);
  if (finder.latitude.value.trim()) form.append("latitude", finder.latitude.value.trim());
  if (finder.longitude.value.trim()) form.append("longitude", finder.longitude.value.trim());
  if (finder.accuracy.value.trim()) form.append("gps_accuracy_m", finder.accuracy.value.trim());
  if (finder.landmark.value.trim()) form.append("landmark_text", finder.landmark.value.trim());
  form.append("limit", "3");
  finder.submit.disabled = true;
  finder.submit.textContent = "기록을 찾는 중...";
  finder.status.textContent = "사진, GPS, 주변 단서를 함께 확인하고 있습니다.";
  try {
    const payload = await api("/api/v1/location-matches", { method: "POST", body: form });
    renderMatchResults(payload);
  } catch (error) {
    finder.status.textContent = error.message;
  } finally {
    finder.submit.disabled = false;
    finder.submit.textContent = "기록 후보 찾기";
  }
}

async function restoreSelectedPhoto() {
  if (state.sourceMode === "upload" && !state.selectedFile) return;
  const form = new FormData();
  form.append("source_mode", state.sourceMode);
  if (state.sourceMode === "upload") form.append("photo", state.selectedFile);
  form.append("use_ai", String(elements.aiToggle.checked));
  if (state.selectedPlace) form.append("place_id", state.selectedPlace.id);
  if (state.sourceMode === "upload") form.append("source_attribution", "Local prototype upload");
  if (state.sourceMode === "upload" && state.selectedMatchCandidate) form.append("matched_asset_id", state.selectedMatchCandidate.asset_id);
  elements.restoreButton.disabled = true;
  elements.restoreButton.textContent = "복원 중...";
  elements.uploadNote.textContent = "원본을 보존하고 결과 기록을 만드는 중입니다.";
  try {
    const record = await api("/api/v1/restorations", { method: "POST", body: form });
    renderResults(record);
    elements.uploadNote.textContent = `복원 기록 ${record.record_id} 생성 완료`;
  } catch (error) {
    elements.uploadNote.textContent = error.message;
  } finally {
    elements.restoreButton.disabled = false;
    elements.restoreButton.textContent = "복원 시작";
  }
}

async function initialize() {
  renderZones();
  try {
    const [health, placeData] = await Promise.all([api("/api/v1/health"), api("/api/v1/places")]);
    elements.apiStatus.textContent = health.ai_mode === "enabled" ? "Local AI ready" : "Local baseline";
    state.places = placeData.places;
    selectPlace(state.places[0]);
  } catch (error) {
    elements.apiStatus.textContent = "API unavailable";
    elements.uploadNote.textContent = error.message;
  }
}

elements.fileInput.addEventListener("change", (event) => {
  state.selectedMatchCandidate = null;
  selectFile(event.target.files[0]);
});
elements.restoreButton.addEventListener("click", restoreSelectedPhoto);
finder.open.addEventListener("click", openFinder);
finder.close.addEventListener("click", closeFinder);
finder.fileInput.addEventListener("change", (event) => selectMatchFile(event.target.files[0]));
finder.submit.addEventListener("click", findHistoricalCandidates);
finder.resultsBack.addEventListener("click", () => showFinderScreen("input"));
finder.detailBack.addEventListener("click", () => showFinderScreen("results"));
document.querySelectorAll(".mode-tab").forEach((button) => button.addEventListener("click", () => {
  state.sourceMode = button.dataset.mode;
  updateSourceMode();
}));
initialize();
