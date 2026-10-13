(function () {
  "use strict";

  const POLL_MS = 3000;
  const TIMEOUT_MS = 5000;
  const MAX_BACKOFF_MS = 60000;
  const STALE_MS = 900000;
  const FUTURE_TOLERANCE_MS = 60000;
  const MAX_FEED_BYTES = 24000;
  const FORBIDDEN_TEXT = /(?:https?:\/\/|[A-Za-z]:[\\/]|\/(?:workspace|home|tmp|etc|var)\/|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+?\d[ -]?){10,}|(?:gh[pousr]_|github_pat_|sk-proj-)[A-Za-z0-9_-]+)/i;
  const TEAMS = [
    { id: "backend", name: "Backend", symbol: "BE" },
    { id: "frontend", name: "Frontend", symbol: "FE" },
    { id: "pemeriksa", name: "Pemeriksa", symbol: "QA" },
    { id: "cms", name: "CMS", symbol: "CM" },
    { id: "kontenseo", name: "Konten SEO", symbol: "SE" },
    { id: "marketing", name: "Marketing", symbol: "MK" },
    { id: "rilis", name: "Rilis", symbol: "RL" },
    { id: "pemantau", name: "Pemantau", symbol: "PM" }
  ];
  const STATUSES = {
    working: { label: "Bekerja", icon: "↻" },
    waiting: { label: "Menunggu", icon: "Ⅱ" },
    done: { label: "Selesai", icon: "✓" },
    blocked: { label: "Terhambat", icon: "!" },
    unassigned: { label: "Belum ditugasi", icon: "−" },
    unknown: { label: "Tidak diketahui", icon: "?" }
  };
  const STAGES = { draft: "Source / draf", tested: "Sudah diuji", live: "Live terverifikasi", unknown: "Belum diketahui" };
  const cards = new Map();
  const ui = {
    badge: document.getElementById("connection-badge"),
    message: document.getElementById("connection-message"),
    refresh: document.getElementById("refresh-button"),
    sourceUpdated: document.getElementById("source-updated"),
    checked: document.getElementById("view-checked"),
    freshness: document.getElementById("freshness-note"),
    counts: document.getElementById("status-counts"),
    grid: document.getElementById("teams"),
    releaseName: document.getElementById("release-heading"),
    releaseStage: document.getElementById("release-stage"),
    releaseSummary: document.getElementById("release-summary"),
    releaseHistory: document.getElementById("release-history"),
    releaseSha: document.getElementById("release-sha"),
    releasePr: document.getElementById("release-pr"),
    releaseObserved: document.getElementById("release-observed")
  };
  const dateFormatter = new Intl.DateTimeFormat("id-ID", {
    timeZone: "UTC", day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23"
  });
  let lastFeed = null;
  let sourceReadable = false;
  let fetchActive = false;
  let activeController = null;
  let pollTimer = null;
  let requestTimer = null;
  let failures = 0;
  let requestHiddenAbort = false;
  let pendingVisibleRefresh = false;

  function isObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function exactFields(value, expected) {
    return isObject(value) && Object.keys(value).length === expected.length && expected.every(function (key) { return Object.prototype.hasOwnProperty.call(value, key); });
  }

  function safeText(value, maxLength) {
    return typeof value === "string" && value.trim().length > 0 && value.length <= maxLength && !/[\u0000-\u001f]/.test(value) && !FORBIDDEN_TEXT.test(value);
  }

  function validTimestamp(value, nullable) {
    if (nullable && value === null) return true;
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value)) return false;
    const millis = Date.parse(value);
    return Number.isFinite(millis) && new Date(millis).toISOString().slice(0, 19) === value.slice(0, 19) && millis <= Date.now() + FUTURE_TOLERANCE_MS;
  }

  function validEvidenceUrl(value) {
    return typeof value === "string" && value.length <= 220 && /^https:\/\/github\.com\/erwin071996\/rumahwebhous\/(?:pull\/\d+|commit\/[0-9a-f]{40}|actions\/runs\/\d+(?:\/job\/\d+)?)$/.test(value);
  }

  function validateFeed(value) {
    if (!exactFields(value, ["schemaVersion", "updatedAt", "staleAfterSeconds", "refreshIntervalMs", "sourceMode", "release", "teams"]) || value.schemaVersion !== 1 || value.staleAfterSeconds !== 900 || value.refreshIntervalMs !== POLL_MS || value.sourceMode !== "report-driven" || !validTimestamp(value.updatedAt, true)) return false;
    if (!exactFields(value.release, ["label", "stage", "sha", "prUrl", "summary", "observedAt"])) return false;
    const release = value.release;
    if (!safeText(release.label, 80) || !Object.prototype.hasOwnProperty.call(STAGES, release.stage) || !safeText(release.summary, 500) || !validTimestamp(release.observedAt, true)) return false;
    if (release.sha !== null && (typeof release.sha !== "string" || !/^[a-f0-9]{40}$/.test(release.sha))) return false;
    if (release.prUrl !== null && !validEvidenceUrl(release.prUrl)) return false;
    if (release.observedAt !== null && Date.parse(release.observedAt) > Date.parse(value.updatedAt)) return false;
    if (!Array.isArray(value.teams) || value.teams.length !== TEAMS.length) return false;
    const ids = new Set();
    for (const team of value.teams) {
      if (!exactFields(team, ["id", "name", "status", "summary", "nextStep", "waitingFor", "observedAt", "evidence"]) || !TEAMS.some(function (expected) { return expected.id === team.id; }) || ids.has(team.id)) return false;
      if (!safeText(team.name, 80) || !Object.prototype.hasOwnProperty.call(STATUSES, team.status) || !safeText(team.summary, 500) || !safeText(team.nextStep, 300) || !validTimestamp(team.observedAt, true)) return false;
      if (team.waitingFor !== null && !safeText(team.waitingFor, 100)) return false;
      if (team.observedAt !== null && Date.parse(team.observedAt) > Date.parse(value.updatedAt)) return false;
      if (team.status !== "unknown" && team.observedAt === null) return false;
      if (!Array.isArray(team.evidence) || team.evidence.length > 5) return false;
      if (["working", "done"].includes(team.status) && team.evidence.length === 0) return false;
      for (const evidence of team.evidence) {
        if (!exactFields(evidence, ["label", "url"]) || !safeText(evidence.label, 80) || !validEvidenceUrl(evidence.url)) return false;
      }
      ids.add(team.id);
    }
    if (value.updatedAt === null && (release.stage !== "unknown" || release.sha !== null || release.prUrl !== null || release.observedAt !== null || value.teams.some(function (team) { return team.status !== "unknown" || team.observedAt !== null; }))) return false;
    return true;
  }

  function formatTimestamp(value) {
    return dateFormatter.format(new Date(value)) + " UTC";
  }

  function setTime(element, value, fallback, prefix) {
    element.textContent = value ? (prefix || "") + formatTimestamp(value) : fallback;
    if (value) element.dateTime = value;
    else element.removeAttribute("datetime");
  }

  function staleReason(observedAt, now) {
    if (!sourceReadable) return "Sumber belum dapat dibaca; status saat ini tidak diketahui.";
    if (lastFeed && lastFeed.updatedAt === null) return "Belum ada bukti sumber; status saat ini tidak diketahui.";
    if (lastFeed && now - Date.parse(lastFeed.updatedAt) > STALE_MS) return "Sumber kedaluwarsa (>15 menit); status saat ini tidak diketahui.";
    if (observedAt === null) return "Waktu bukti belum tersedia; status saat ini tidak diketahui.";
    if (now - Date.parse(observedAt) > STALE_MS) return "Bukti kedaluwarsa (>15 menit); status saat ini tidak diketahui.";
    return "";
  }

  function setConnection(state, badgeText, message) {
    ui.badge.dataset.state = state;
    ui.badge.textContent = badgeText;
    if (ui.message.textContent !== message) ui.message.textContent = message;
  }

  function createCards() {
    const template = document.getElementById("team-card-template");
    const fragment = document.createDocumentFragment();
    TEAMS.forEach(function (team) {
      const node = template.content.firstElementChild.cloneNode(true);
      node.id = "team-" + team.id;
      node.querySelector(".team-name").textContent = team.name;
      node.querySelector(".team-symbol").textContent = team.symbol;
      cards.set(team.id, {
        node: node,
        name: node.querySelector(".team-name"),
        label: node.querySelector(".status-label"),
        icon: node.querySelector(".status-icon"),
        summary: node.querySelector(".team-summary"),
        history: node.querySelector(".team-history"),
        next: node.querySelector(".team-next"),
        waiting: node.querySelector(".team-waiting"),
        observed: node.querySelector(".team-observed"),
        evidence: node.querySelector(".team-evidence")
      });
      fragment.appendChild(node);
    });
    ui.grid.replaceChildren(fragment);
  }

  function renderEvidence(element, evidence) {
    const fragment = document.createDocumentFragment();
    evidence.forEach(function (item) {
      const link = document.createElement("a");
      link.textContent = item.label + " ↗";
      link.href = item.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      fragment.appendChild(link);
    });
    element.replaceChildren(fragment);
  }

  function render() {
    const now = Date.now();
    const counts = { working: 0, waiting: 0, done: 0, blocked: 0, unassigned: 0, unknown: 0 };
    let staleCount = 0;
    TEAMS.forEach(function (expected) {
      const card = cards.get(expected.id);
      const team = lastFeed ? lastFeed.teams.find(function (item) { return item.id === expected.id; }) : null;
      const reason = team ? staleReason(team.observedAt, now) : "Bukti status belum tersedia.";
      const status = team && !reason ? team.status : "unknown";
      counts[status] += 1;
      if (team && reason) staleCount += 1;
      card.node.dataset.status = status;
      card.name.textContent = team ? team.name : expected.name;
      card.label.textContent = STATUSES[status].label;
      card.icon.textContent = STATUSES[status].icon;
      card.summary.textContent = team ? team.summary : "Bukti status belum tersedia.";
      card.history.hidden = !reason;
      card.history.textContent = reason + (team ? " Status terakhir tercatat: " + STATUSES[team.status].label + "." : "");
      card.next.textContent = team ? team.nextStep : "Menunggu laporan terverifikasi.";
      card.waiting.textContent = team ? (team.waitingFor || "Tidak ada yang disebut dalam laporan") : "Belum diketahui";
      setTime(card.observed, team ? team.observedAt : null, "Waktu bukti belum tersedia", "Bukti: ");
      renderEvidence(card.evidence, team ? team.evidence : []);
    });
    const countFragment = document.createDocumentFragment();
    Object.keys(STATUSES).forEach(function (status) {
      const item = document.createElement("span");
      item.className = "count-item";
      const number = document.createElement("strong");
      number.textContent = String(counts[status]);
      item.appendChild(number);
      item.appendChild(document.createTextNode(STATUSES[status].label));
      countFragment.appendChild(item);
    });
    ui.counts.replaceChildren(countFragment);
    ui.freshness.textContent = lastFeed && lastFeed.updatedAt === null ? "Belum ada bukti sumber · seluruh status tidak diketahui" : (staleCount ? staleCount + " kartu tanpa bukti segar · status tidak diketahui" : (lastFeed ? "Status mengikuti waktu bukti pada tiap kartu" : "Status tanpa bukti segar: tidak diketahui"));
    setTime(ui.sourceUpdated, lastFeed ? lastFeed.updatedAt : null, "Belum tersedia");
    if (lastFeed) {
      const release = lastFeed.release;
      const reason = staleReason(release.observedAt, now);
      const stage = reason ? "unknown" : release.stage;
      ui.releaseName.textContent = release.label;
      ui.releaseStage.dataset.stage = stage;
      ui.releaseStage.textContent = STAGES[stage];
      ui.releaseSummary.textContent = release.summary;
      ui.releaseHistory.hidden = !reason;
      ui.releaseHistory.textContent = reason + " Tahap terakhir tercatat: " + STAGES[release.stage] + ".";
      ui.releaseSha.textContent = release.sha || "SHA belum tersedia";
      ui.releasePr.hidden = !release.prUrl;
      if (release.prUrl) ui.releasePr.href = release.prUrl;
      else ui.releasePr.removeAttribute("href");
      setTime(ui.releaseObserved, release.observedAt, "Waktu bukti belum tersedia", "Bukti: ");
    }
    ui.grid.setAttribute("aria-busy", "false");
  }

  function clearPollTimer() {
    if (pollTimer !== null) clearTimeout(pollTimer);
    pollTimer = null;
  }

  function schedulePoll(delay) {
    clearPollTimer();
    if (!document.hidden) pollTimer = setTimeout(poll, delay);
  }

  async function poll() {
    clearPollTimer();
    if (document.hidden || fetchActive) return;
    render();
    fetchActive = true;
    requestHiddenAbort = false;
    ui.refresh.disabled = true;
    activeController = new AbortController();
    let timedOut = false;
    requestTimer = setTimeout(function () {
      timedOut = true;
      if (activeController) activeController.abort();
    }, TIMEOUT_MS);
    let nextDelay = POLL_MS;
    try {
      const response = await fetch("./status.json", {
        cache: "no-store", credentials: "same-origin", signal: activeController.signal,
        headers: { Accept: "application/json" }
      });
      if (!response.ok) throw new Error("http");
      const contentLength = Number(response.headers.get("content-length"));
      if (contentLength > MAX_FEED_BYTES) throw new Error("size");
      const raw = await response.text();
      if (new TextEncoder().encode(raw).byteLength > MAX_FEED_BYTES) throw new Error("size");
      const feed = JSON.parse(raw);
      if (!validateFeed(feed)) throw new Error("schema");
      if (document.hidden) return;
      lastFeed = feed;
      sourceReadable = true;
      failures = 0;
      setTime(ui.checked, new Date().toISOString(), "Belum diperiksa");
      render();
      if (feed.updatedAt === null) {
        setConnection("unknown", "Belum ada bukti sumber", "JSON terbaca tanpa bukti sumber. Seluruh status tetap tidak diketahui.");
      } else {
        const sourceStale = Date.now() - Date.parse(feed.updatedAt) > STALE_MS;
        setConnection(sourceStale ? "stale" : "fresh", sourceStale ? "Sumber kedaluwarsa" : "Sumber berhasil dibaca", sourceStale ? "JSON terbaca, tetapi waktu pembaruan sumber lebih lama dari 15 menit." : "Pemeriksaan tampilan berhasil. Status tim tetap mengikuti waktu bukti pada kartu.");
      }
    } catch (_) {
      if ((document.hidden || requestHiddenAbort) && !timedOut) return;
      sourceReadable = false;
      failures += 1;
      nextDelay = Math.min(MAX_BACKOFF_MS, POLL_MS * Math.pow(2, Math.min(failures, 5)));
      setTime(ui.checked, new Date().toISOString(), "Belum diperiksa");
      render();
      setConnection("error", "Sumber belum terbaca", "Status saat ini tidak diketahui. Mencoba kembali dalam " + String(nextDelay / 1000) + " detik; bukti terakhir tetap ditampilkan sebagai riwayat.");
    } finally {
      if (requestTimer !== null) clearTimeout(requestTimer);
      requestTimer = null;
      activeController = null;
      fetchActive = false;
      ui.refresh.disabled = false;
      schedulePoll(pendingVisibleRefresh ? 0 : nextDelay);
      pendingVisibleRefresh = false;
    }
  }

  ui.refresh.addEventListener("click", function () { if (!fetchActive && !document.hidden) poll(); });
  document.addEventListener("visibilitychange", function () {
    clearPollTimer();
    if (document.hidden) {
      if (activeController) {
        requestHiddenAbort = true;
        activeController.abort();
      }
      sourceReadable = false;
      render();
      setConnection("paused", "Tab tidak terlihat", "Pemeriksaan sumber berhenti saat tab tidak terlihat. Status akan diperiksa kembali saat tab dibuka.");
      return;
    }
    render();
    if (!fetchActive) poll();
    else pendingVisibleRefresh = true;
  });
  window.addEventListener("online", function () { if (!fetchActive && !document.hidden) poll(); });
  createCards();
  render();
  if (!document.hidden) poll();
  else setConnection("paused", "Tab tidak terlihat", "Pemeriksaan sumber dimulai saat tab terlihat.");
}());
