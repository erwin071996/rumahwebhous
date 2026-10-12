/* Progressive portfolio enhancements. No form submission or analytics. */
(function () {
  "use strict";
  /* Keep baseline menu click behavior; add explicit focus and Escape cleanup. */
  const menu = document.querySelector(".menu-toggle");
  const nav = document.getElementById("site-nav");
  const services = document.querySelector(".nav-services");
  const summary = services && services.querySelector("summary");
  function closeNavigation(focusMenu) {
    if (services) services.open = false;
    if (nav) nav.removeAttribute("data-open");
    if (menu) menu.setAttribute("aria-expanded", "false");
    if (focusMenu && menu) menu.focus();
  }
  if (menu && nav) {
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape" || document.querySelector("dialog[open]")) return;
      const menuOpen = menu.getAttribute("aria-expanded") === "true" || nav.hasAttribute("data-open");
      const servicesOpen = services && services.open;
      if (!menuOpen && !servicesOpen) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const mobile = window.matchMedia("(max-width: 1020px)").matches;
      closeNavigation(mobile || menuOpen);
      if (!mobile && !menuOpen && summary) summary.focus();
    }, true);
    nav.addEventListener("click", function (event) {
      const anchor = event.target.closest("a[href]");
      if (!anchor) return;
      const targetUrl = new URL(anchor.href, location.href);
      closeNavigation(false);
      if (targetUrl.origin === location.origin && targetUrl.pathname === location.pathname && targetUrl.hash) {
        const target = document.getElementById(decodeURIComponent(targetUrl.hash.slice(1)));
        if (target) {
          if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
          setTimeout(function () { target.focus({ preventScroll: true }); }, 0);
        }
      }
    });
    document.addEventListener("click", function (event) {
      if (!nav.contains(event.target) && !menu.contains(event.target)) closeNavigation(false);
    });
    const breakpoint = window.matchMedia("(max-width: 1020px)");
    if (typeof breakpoint.addEventListener === "function") breakpoint.addEventListener("change", function () {
      const active = document.activeElement;
      const wasInNav = nav.contains(active);
      const wasInServices = services && services.contains(active);
      const wasMenu = menu.contains(active);
      closeNavigation(false);
      if (breakpoint.matches && (wasInNav || wasMenu)) menu.focus();
      else if (!breakpoint.matches && (wasMenu || wasInServices) && summary) summary.focus();
    });
  }
  const filters = Array.from(document.querySelectorAll(".real-filter"));
  const cards = Array.from(document.querySelectorAll(".real-card"));
  const count = document.getElementById("gallery-result-count");
  function filterGallery(button) {
    const category = button.dataset.filter;
    let visible = 0;
    filters.forEach(function (item) {
      const selected = item === button;
      item.classList.toggle("active", selected);
      item.setAttribute("aria-pressed", String(selected));
    });
    cards.forEach(function (card) {
      const hidden = category !== "all" && card.dataset.cat !== category;
      card.hidden = hidden;
      card.classList.toggle("real-hidden", hidden);
      if (!hidden) visible += 1;
    });
    if (count) count.textContent = visible + " proyek ditampilkan" + (category === "all" ? "." : " · " + button.textContent.trim() + ".");
  }
  filters.forEach(function (button) {
    button.setAttribute("aria-controls", "project-gallery");
    button.disabled = false;
    button.addEventListener("click", function () { filterGallery(button); });
  });
  const selected = filters.find(function (button) { return button.getAttribute("aria-pressed") === "true"; });
  if (selected) filterGallery(selected);

  const dialog = document.getElementById("real-video-dialog");
  const video = document.getElementById("real-video-player");
  const title = document.getElementById("real-video-title");
  const status = document.getElementById("real-video-status");
  const source = document.getElementById("real-video-source");
  const closeButton = document.getElementById("real-video-close");
  let opener = null;
  let playbackGeneration = 0;
  let dialogUsesFallback = false;
  function isVideoOpen() {
    return !!dialog && (dialog.open === true || dialog.hasAttribute("open"));
  }
  function closeVideo() {
    if (!dialog || !video) return;
    playbackGeneration += 1;
    video.pause();
    video.removeAttribute("src");
    video.load();
    if (isVideoOpen()) {
      if (!dialogUsesFallback && typeof dialog.close === "function") dialog.close();
      else { dialog.removeAttribute("open"); if (opener) opener.focus(); }
    }
  }
  if (dialog && video && title && closeButton && status && source) {
    dialog.setAttribute("role", "dialog");
    document.querySelectorAll(".real-video").forEach(function (button) {
      button.type = "button";
      button.disabled = false;
      button.addEventListener("click", function () {
        const url = button.dataset.video;
        if (!url) return;
        opener = button;
        const generation = ++playbackGeneration;
        source.href = url;
        status.textContent = "Memuat dokumentasi video…";
        title.textContent = button.dataset.title || "Dokumentasi video proyek";
        video.src = url;
        dialogUsesFallback = typeof dialog.showModal !== "function";
        dialog.setAttribute("aria-modal", String(!dialogUsesFallback));
        dialog.setAttribute("data-video-fallback", String(dialogUsesFallback));
        if (dialogUsesFallback) {
          status.textContent = "Peramban ini belum mendukung pemutar dialog. Buka file video melalui tautan.";
          dialog.setAttribute("open", "");
          closeButton.focus();
          return;
        }
        dialog.showModal();
        closeButton.focus();
        video.play().catch(function () {
          if (generation === playbackGeneration && isVideoOpen() && !video.error) status.textContent = "Tekan tombol putar untuk melihat dokumentasi.";
        });
      });
    });
    video.addEventListener("playing", function () { if (isVideoOpen() && video.hasAttribute("src")) status.textContent = "Dokumentasi video sedang diputar."; });
    video.addEventListener("error", function () {
      if (isVideoOpen()) status.textContent = "Video belum dapat dimuat. Coba buka file video, atau bahas dokumentasi proyek dengan tim kami.";
    });
    closeButton.addEventListener("click", closeVideo);
    dialog.addEventListener("click", function (event) { if (event.target === dialog) closeVideo(); });
    dialog.addEventListener("cancel", function (event) { event.preventDefault(); closeVideo(); });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && isVideoOpen() && dialogUsesFallback) {
        event.preventDefault();
        event.stopImmediatePropagation();
        closeVideo();
      }
    }, true);
    dialog.addEventListener("close", function () {
      if (isVideoOpen()) return;
      playbackGeneration += 1;
      video.pause();
      video.removeAttribute("src");
      video.load();
      if (opener && document.contains(opener)) opener.focus();
    });
  }

  const copy = document.getElementById("copy-portfolio-link");
  const print = document.getElementById("print-portfolio");
  const toolStatus = document.getElementById("client-tool-status");
  const shareFallback = document.getElementById("portfolio-share-fallback");
  const shareUrl = document.getElementById("portfolio-share-url");
  if (copy && toolStatus) copy.disabled = false;
  if (copy && toolStatus) copy.addEventListener("click", async function () {
    const url = new URL("/projects.html#studi-kasus", location.origin).href;
    if (shareFallback) shareFallback.hidden = true;
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(url);
      toolStatus.textContent = "Tautan portofolio tersalin.";
    } catch (error) {
      if (shareFallback && shareUrl) {
        shareUrl.value = url;
        shareFallback.hidden = false;
        shareUrl.focus();
        shareUrl.select();
        toolStatus.textContent = "Salin tautan yang dipilih melalui menu perangkat atau Ctrl+C.";
      } else toolStatus.textContent = "Salin alamat halaman dari bilah alamat peramban untuk membagikan portofolio.";
    }
  });
  if (print) print.disabled = false;
  if (print) print.addEventListener("click", function () { window.print(); });
})();
