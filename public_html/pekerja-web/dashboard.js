(function () {
  "use strict";

  const POLL_MS = 3000;
  const TIMEOUT_MS = 5000;
  const MAX_BACKOFF_MS = 60000;
  const STALE_MS = 900000;
  const FUTURE_TOLERANCE_MS = 60000;
  const MAX_FEED_BYTES = 24000;
  const FORBIDDEN_TEXT = /(?:https?:\/\/|[A-Za-z]:[\\/]|\/(?:workspace|home|tmp|etc|var)\/|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+?\d[ -]?){10,}|(?:gh[pousr]_|github_pat_|sk-proj-)[A-Za-z0-9_-]+)/i;
  const CHARACTERS = {"backend":{"persona":"Byte","roleLabel":"Backend","accent":"#B96248","viewBox":"0 0 64 64","parts":[{"tag":"circle","attrs":{"cx":32,"cy":32,"r":30,"fill":"#fdd"}},{"tag":"rect","attrs":{"x":17,"y":42,"width":30,"height":18,"rx":9,"fill":"#b64"}},{"tag":"rect","attrs":{"x":22,"y":48,"width":20,"height":9,"rx":4,"fill":"#fdb"}},{"tag":"line","attrs":{"x1":32,"y1":16,"x2":32,"y2":8,"stroke":"#854","stroke-width":2,"stroke-linecap":"round"}},{"tag":"circle","attrs":{"cx":32,"cy":7,"r":4,"fill":"#ea5"}},{"tag":"rect","attrs":{"x":10,"y":24,"width":8,"height":16,"rx":4,"fill":"#b64"}},{"tag":"rect","attrs":{"x":46,"y":24,"width":8,"height":16,"rx":4,"fill":"#b64"}},{"tag":"rect","attrs":{"x":16,"y":16,"width":32,"height":30,"rx":10,"fill":"#eb8"}},{"tag":"rect","attrs":{"x":20,"y":21,"width":24,"height":19,"rx":6,"fill":"#fec"}},{"tag":"path","attrs":{"d":"M23 29a2 2 0 1 0 4 0a2 2 0 1 0-4 0m14 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0","fill":"#533","class":"avatar-eyes"}},{"tag":"rect","attrs":{"x":27,"y":35,"width":10,"height":3,"rx":1.5,"fill":"#c76"}}]},"frontend":{"persona":"Pixel","roleLabel":"Frontend","accent":"#D89050","viewBox":"0 0 64 64","parts":[{"tag":"circle","attrs":{"cx":32,"cy":32,"r":30,"fill":"#fed"}},{"tag":"rect","attrs":{"x":16,"y":43,"width":32,"height":18,"rx":9,"fill":"#965"}},{"tag":"path","attrs":{"d":"M15 25 18 9 29 19M35 19 46 9 49 27","fill":"#d85"}},{"tag":"path","attrs":{"d":"M19 22 20 15 26 21M39 21 44 15 45 23","fill":"#eb9"}},{"tag":"ellipse","attrs":{"cx":32,"cy":31,"rx":18,"ry":17,"fill":"#ea6"}},{"tag":"path","attrs":{"d":"M22 34q10-7 20 0v7q-10 9-20 0z","fill":"#fec"}},{"tag":"path","attrs":{"d":"M22 29a2 2 0 1 0 4 0a2 2 0 1 0-4 0m16 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0","fill":"#533","class":"avatar-eyes"}},{"tag":"path","attrs":{"d":"M29 34h6l-3 4z","fill":"#965"}},{"tag":"path","attrs":{"d":"M32 38q-4 4-7 0m7 0q4 4 7 0","fill":"none","stroke":"#744","stroke-width":1.8,"stroke-linecap":"round"}},{"tag":"ellipse","attrs":{"cx":29,"cy":16,"rx":17,"ry":6,"fill":"#788"}},{"tag":"line","attrs":{"x1":48,"y1":55,"x2":53,"y2":40,"stroke":"#854","stroke-width":3,"stroke-linecap":"round"}},{"tag":"path","attrs":{"d":"M50 41q-4-8 4-10 6 5-1 11z","fill":"#d88"}}]},"pemeriksa":{"persona":"Lensa","roleLabel":"Pemeriksa","accent":"#88745B","viewBox":"0 0 64 64","parts":[{"tag":"circle","attrs":{"cx":32,"cy":32,"r":30,"fill":"#eed"}},{"tag":"ellipse","attrs":{"cx":32,"cy":47,"rx":17,"ry":14,"fill":"#875"}},{"tag":"path","attrs":{"d":"M15 24 17 13 28 20h8l11-7 2 12v17q-17 16-34 0z","fill":"#975"}},{"tag":"ellipse","attrs":{"cx":24,"cy":30,"rx":10,"ry":12,"fill":"#fdb"}},{"tag":"ellipse","attrs":{"cx":40,"cy":30,"rx":10,"ry":12,"fill":"#fdb"}},{"tag":"circle","attrs":{"cx":24,"cy":29,"r":7,"fill":"none","stroke":"#677","stroke-width":2}},{"tag":"circle","attrs":{"cx":40,"cy":29,"r":7,"fill":"none","stroke":"#677","stroke-width":2}},{"tag":"path","attrs":{"d":"M22 29a2 2 0 1 0 4 0a2 2 0 1 0-4 0m16 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0","fill":"#533","class":"avatar-eyes"}},{"tag":"path","attrs":{"d":"M28 36h8l-4 6z","fill":"#d95"}},{"tag":"rect","attrs":{"x":21,"y":12,"width":23,"height":7,"rx":3,"fill":"#677"}},{"tag":"rect","attrs":{"x":14,"y":18,"width":36,"height":4,"rx":2,"fill":"#677"}}]},"cms":{"persona":"Keeper","roleLabel":"CMS","accent":"#6F8B68","viewBox":"0 0 64 64","parts":[{"tag":"circle","attrs":{"cx":32,"cy":32,"r":30,"fill":"#eed"}},{"tag":"ellipse","attrs":{"cx":32,"cy":45,"rx":20,"ry":15,"fill":"#786"}},{"tag":"path","attrs":{"d":"M19 40 25 34h14l6 6-3 12H22z","fill":"#8a7"}},{"tag":"ellipse","attrs":{"cx":32,"cy":29,"rx":15,"ry":14,"fill":"#bc9"}},{"tag":"rect","attrs":{"x":16,"y":27,"width":8,"height":5,"rx":2,"fill":"#676"}},{"tag":"rect","attrs":{"x":25,"y":25,"width":10,"height":7,"rx":3,"fill":"none","stroke":"#676","stroke-width":1.5}},{"tag":"rect","attrs":{"x":36,"y":25,"width":9,"height":7,"rx":3,"fill":"none","stroke":"#676","stroke-width":1.5}},{"tag":"path","attrs":{"d":"M27 29a2 2 0 1 0 4 0a2 2 0 1 0-4 0m11 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0","fill":"#533","class":"avatar-eyes"}},{"tag":"path","attrs":{"d":"M28 36q4 4 8 0","fill":"none","stroke":"#744","stroke-width":1.8,"stroke-linecap":"round"}},{"tag":"path","attrs":{"d":"M17 46q8-3 15 1 7-4 15-1v12q-8-3-15 0-7-3-15 0z","fill":"#feb"}},{"tag":"line","attrs":{"x1":37,"y1":51,"x2":43,"y2":50,"stroke":"#c96","stroke-width":1.5,"stroke-linecap":"round"}},{"tag":"circle","attrs":{"cx":17,"cy":48,"r":4,"fill":"#bc9"}},{"tag":"circle","attrs":{"cx":47,"cy":48,"r":4,"fill":"#bc9"}}]},"kontenseo":{"persona":"Quill","roleLabel":"Konten & SEO","accent":"#DC8C50","viewBox":"0 0 64 64","parts":[{"tag":"circle","attrs":{"cx":32,"cy":32,"r":30,"fill":"#fdd"}},{"tag":"rect","attrs":{"x":16,"y":43,"width":31,"height":17,"rx":8,"fill":"#a65"}},{"tag":"path","attrs":{"d":"M14 27 16 10 29 20h6l13-10 2 17-6 15q-12 12-24 0z","fill":"#d85"}},{"tag":"path","attrs":{"d":"M19 23 19 16 25 23M39 23 45 16 45 23","fill":"#fdb"}},{"tag":"path","attrs":{"d":"M17 31q8-1 15 8 7-9 15-8l-5 12q-10 10-20 0z","fill":"#fec"}},{"tag":"path","attrs":{"d":"M22 29a2 2 0 1 0 4 0a2 2 0 1 0-4 0m16 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0","fill":"#533","class":"avatar-eyes"}},{"tag":"path","attrs":{"d":"M28 37q4-3 8 0l-4 4z","fill":"#643"}},{"tag":"path","attrs":{"d":"M32 41v3m-4 0q4 3 8 0","fill":"none","stroke":"#744","stroke-width":1.8,"stroke-linecap":"round"}},{"tag":"rect","attrs":{"x":19,"y":49,"width":18,"height":9,"rx":2,"fill":"#edb"}},{"tag":"path","attrs":{"d":"M46 55q-2-17 9-23 2 13-9 23z","fill":"#da6"}},{"tag":"line","attrs":{"x1":46,"y1":55,"x2":53,"y2":36,"stroke":"#865","stroke-width":1.5,"stroke-linecap":"round"}}]},"marketing":{"persona":"Spark","roleLabel":"Marketing","accent":"#DDAA58","viewBox":"0 0 64 64","parts":[{"tag":"circle","attrs":{"cx":32,"cy":32,"r":30,"fill":"#eec"}},{"tag":"ellipse","attrs":{"cx":29,"cy":43,"rx":16,"ry":17,"fill":"#da5"}},{"tag":"path","attrs":{"d":"M18 40q-8 1-7 14 9 4 13-5z","fill":"#897"}},{"tag":"path","attrs":{"d":"M38 40q8 0 8 12-8 5-11-3z","fill":"#897"}},{"tag":"circle","attrs":{"cx":29,"cy":27,"r":15,"fill":"#ec7"}},{"tag":"path","attrs":{"d":"M20 15q-1-8 5-9l4 9q2-9 7-7l-2 8z","fill":"#da5"}},{"tag":"path","attrs":{"d":"M20 26a2 2 0 1 0 4 0a2 2 0 1 0-4 0m13 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0","fill":"#533","class":"avatar-eyes"}},{"tag":"path","attrs":{"d":"M26 31h8l-4 7-4-3z","fill":"#c75"}},{"tag":"circle","attrs":{"cx":18,"cy":33,"r":3,"fill":"#ea7"}},{"tag":"path","attrs":{"d":"M38 39h7l9-6v19l-9-6h-7z","fill":"#b65"}},{"tag":"rect","attrs":{"x":38,"y":40,"width":6,"height":5,"rx":2,"fill":"#fdb"}},{"tag":"line","attrs":{"x1":45,"y1":47,"x2":47,"y2":54,"stroke":"#954","stroke-width":3,"stroke-linecap":"round"}},{"tag":"line","attrs":{"x1":57,"y1":42,"x2":61,"y2":42,"stroke":"#c96","stroke-width":1.5,"stroke-linecap":"round"}}]},"rilis":{"persona":"Orbit","roleLabel":"Rilis","accent":"#A9796B","viewBox":"0 0 64 64","parts":[{"tag":"circle","attrs":{"cx":32,"cy":32,"r":30,"fill":"#edd"}},{"tag":"rect","attrs":{"x":15,"y":43,"width":34,"height":18,"rx":10,"fill":"#da8"}},{"tag":"rect","attrs":{"x":23,"y":48,"width":18,"height":10,"rx":4,"fill":"#fed"}},{"tag":"circle","attrs":{"cx":32,"cy":28,"r":21,"fill":"#a76"}},{"tag":"rect","attrs":{"x":8,"y":24,"width":7,"height":12,"rx":3,"fill":"#db9"}},{"tag":"rect","attrs":{"x":49,"y":24,"width":7,"height":12,"rx":3,"fill":"#db9"}},{"tag":"circle","attrs":{"cx":32,"cy":28,"r":17,"fill":"#fec"}},{"tag":"path","attrs":{"d":"M18 27q1-15 14-15t14 15z","fill":"#766"}},{"tag":"ellipse","attrs":{"cx":32,"cy":29,"rx":12,"ry":13,"fill":"#ea8"}},{"tag":"path","attrs":{"d":"M20 24q7 1 11-7 5 8 13 8l-1-8-22-1z","fill":"#855"}},{"tag":"path","attrs":{"d":"M23 29a2 2 0 1 0 4 0a2 2 0 1 0-4 0m14 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0","fill":"#533","class":"avatar-eyes"}},{"tag":"path","attrs":{"d":"M28 36q4 4 8 0","fill":"none","stroke":"#744","stroke-width":1.8,"stroke-linecap":"round"}},{"tag":"path","attrs":{"d":"M20 17q-4 4-4 11","fill":"none","stroke":"#ffe","stroke-width":2.5,"stroke-linecap":"round"}},{"tag":"path","attrs":{"d":"M29 55 32 49 35 55 32 54z","fill":"#a76"}}]},"pemantau":{"persona":"Echo","roleLabel":"Pemantau","accent":"#8B6E87","viewBox":"0 0 64 64","parts":[{"tag":"circle","attrs":{"cx":32,"cy":32,"r":30,"fill":"#edd"}},{"tag":"rect","attrs":{"x":17,"y":43,"width":31,"height":18,"rx":9,"fill":"#868"}},{"tag":"ellipse","attrs":{"cx":32,"cy":29,"rx":14,"ry":17,"fill":"#eb9"}},{"tag":"path","attrs":{"d":"M18 27q-2-17 12-17 13-1 16 15l-7-5-7 3-6-4-6 8z","fill":"#755"}},{"tag":"path","attrs":{"d":"M16 28v-5q0-16 16-16 16 0 16 16v5","fill":"none","stroke":"#868","stroke-width":4,"stroke-linecap":"round"}},{"tag":"rect","attrs":{"x":12,"y":24,"width":8,"height":16,"rx":4,"fill":"#868"}},{"tag":"rect","attrs":{"x":44,"y":24,"width":8,"height":16,"rx":4,"fill":"#868"}},{"tag":"line","attrs":{"x1":16,"y1":24,"x2":12,"y2":13,"stroke":"#868","stroke-width":2.5,"stroke-linecap":"round"}},{"tag":"circle","attrs":{"cx":11,"cy":10,"r":3,"fill":"#da6"}},{"tag":"path","attrs":{"d":"M23 29a2 2 0 1 0 4 0a2 2 0 1 0-4 0m14 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0","fill":"#533","class":"avatar-eyes"}},{"tag":"path","attrs":{"d":"M28 36q4 4 8 0","fill":"none","stroke":"#744","stroke-width":1.8,"stroke-linecap":"round"}},{"tag":"path","attrs":{"d":"M49 37q-4 7-12 5","fill":"none","stroke":"#755","stroke-width":2,"stroke-linecap":"round"}},{"tag":"rect","attrs":{"x":33,"y":40,"width":7,"height":4,"rx":2,"fill":"#755"}},{"tag":"circle","attrs":{"cx":32,"cy":52,"r":6,"fill":"#edb"}},{"tag":"path","attrs":{"d":"M32 52v-4m0 4 3-2","fill":"none","stroke":"#868","stroke-width":1.5,"stroke-linecap":"round"}}]}};
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
  const routes = new Map();
  const ui = {
    badge: document.getElementById("connection-badge"),
    message: document.getElementById("connection-message"),
    refresh: document.getElementById("refresh-button"),
    sourceUpdated: document.getElementById("source-updated"),
    checked: document.getElementById("view-checked"),
    freshness: document.getElementById("freshness-note"),
    counts: document.getElementById("status-counts"),
    grid: document.getElementById("teams"),
    routes: document.getElementById("activity-routes"),
    routeNote: document.getElementById("route-note"),
    releaseName: document.getElementById("release-heading"),
    releaseStage: document.getElementById("release-stage"),
    releaseSummary: document.getElementById("release-summary"),
    releaseHistory: document.getElementById("release-history"),
    releaseSha: document.getElementById("release-sha"),
    releasePr: document.getElementById("release-pr"),
    releaseObserved: document.getElementById("release-observed")
  };
  const dateFormatter = new Intl.DateTimeFormat("id-ID", {
    timeZone: "Asia/Makassar", day: "2-digit", month: "short", year: "numeric",
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
    return dateFormatter.format(new Date(value)) + " WITA";
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
      node.querySelector(".team-symbol").replaceChildren(characterIcon(team.id));
      node.querySelector(".character-name").textContent = CHARACTERS[team.id].persona;
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

  function element(tag, className, text) {
    const node = document.createElement(tag);
    node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function svgNode(tag, attributes) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.keys(attributes).forEach(function (name) { node.setAttribute(name, attributes[name]); });
    return node;
  }

  function characterIcon(id) {
    const art = CHARACTERS[id];
    const icon = svgNode("svg", { viewBox: art.viewBox, class: "avatar-character", "aria-hidden": "true", focusable: "false" });
    art.parts.forEach(function (part) { icon.appendChild(svgNode(part.tag, part.attrs)); });
    return icon;
  }

  function createRoutes() {
    const fragment = document.createDocumentFragment();
    TEAMS.forEach(function (team) {
      const node = element("article", "activity-route");
      node.dataset.status = "unknown";
      node.setAttribute("aria-label", "Jalur status " + team.name);
      const identity = element("div", "route-identity");
      const symbol = element("span", "route-symbol");
      symbol.appendChild(characterIcon(team.id));
      symbol.setAttribute("aria-hidden", "true");
      const name = element("h3", "route-name", team.name);
      identity.appendChild(symbol);
      const names = element("div", "route-names");
      names.appendChild(name);
      names.appendChild(element("span", "character-name", CHARACTERS[team.id].persona));
      identity.appendChild(names);
      const track = element("div", "route-track");
      track.setAttribute("aria-hidden", "true");
      const line = svgNode("svg", { viewBox: "0 0 240 64", preserveAspectRatio: "none", class: "route-line" });
      line.appendChild(svgNode("path", { d: "M4 36C30 36 33 15 62 15S92 52 120 32S174 16 194 32S219 42 236 27", fill: "none" }));
      line.appendChild(svgNode("circle", { cx: "4", cy: "36", r: "3" }));
      line.appendChild(svgNode("circle", { cx: "236", cy: "27", r: "3" }));
      const runner = element("span", "route-runner");
      const icon = element("span", "runner-icon");
      icon.appendChild(characterIcon(team.id));
      runner.appendChild(icon);
      track.appendChild(line);
      track.appendChild(runner);
      const state = element("div", "route-state");
      const label = element("span", "route-status-label");
      const detail = element("span", "route-status-detail");
      state.appendChild(label);
      state.appendChild(detail);
      node.appendChild(identity);
      node.appendChild(track);
      node.appendChild(state);
      routes.set(team.id, { node: node, name: name, label: label, detail: detail, icon: icon, status: null });
      fragment.appendChild(node);
    });
    ui.routes.replaceChildren(fragment);
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
      const route = routes.get(expected.id);
      route.node.dataset.status = status;
      route.name.textContent = team ? team.name : expected.name;
      route.label.textContent = STATUSES[status].label;
      const routeDetails = { working: "Bukti kerja masih segar", waiting: "Menunggu langkah berikut", done: "Hasil tim selesai", blocked: "Ada hambatan tercatat", unassigned: "Belum ada penugasan", unknown: "Belum ada bukti segar" };
      route.detail.textContent = routeDetails[status];
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
    ui.routeNote.textContent = counts.working ? counts.working + " tim dengan bukti kerja segar" : "Belum ada tim dengan bukti kerja segar";
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
    ui.routes.setAttribute("aria-busy", "false");
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
  createRoutes();
  render();
  if (!document.hidden) poll();
  else setConnection("paused", "Tab tidak terlihat", "Pemeriksaan sumber dimulai saat tab terlihat.");
}());
