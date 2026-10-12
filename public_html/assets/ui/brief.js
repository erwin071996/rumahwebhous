/* 3DKan brief: browser-only message preparation. No requests or storage. */
(function (root, factory) {
  "use strict";
  const api = factory(root);
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.KanBrief = api;
  if (root.document) {
    const boot = function () {
      root.document.querySelectorAll("form[data-brief-form]").forEach(function (form) {
        api.bind(form, form.getAttribute("data-brief-form"));
      });
    };
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", boot, { once: true });
    else boot();
  }
})(typeof globalThis === "object" ? globalThis : this, function (root) {
  "use strict";
  const RECIPIENT = "6285340382029";
  const MAX_URL_LENGTH = 8000;
  const TYPES = Object.freeze(["Huruf timbul", "Neon box", "Papan nama / shop sign", "Neon flex", "Corporate signage", "Interior signage", "Multi-lokasi", "Lainnya"]);
  const FIELDS = Object.freeze({
    name: { label: "Nama / PIC", maxLength: 100 },
    pic: { label: "Nama PIC", maxLength: 100 },
    company: { label: "Usaha / perusahaan", maxLength: 160 },
    type: { label: "Kebutuhan", maxLength: 40 },
    location: { label: "Lokasi", maxLength: 160 },
    size: { label: "Ukuran perkiraan", maxLength: 120 },
    points: { label: "Jumlah titik", maxLength: 6 },
    target: { label: "Target waktu", maxLength: 120 },
    note: { label: "Catatan kebutuhan", maxLength: 1000 }
  });
  const KEYS = Object.freeze({
    home: ["name", "company", "type", "location", "size", "points", "note"],
    project: ["company", "pic", "type", "points", "location", "target", "note"]
  });

  function getKeys(kind) {
    if (!Object.prototype.hasOwnProperty.call(KEYS, kind)) throw new Error("Unknown brief form kind");
    return KEYS[kind];
  }

  function wellFormed(text) {
    for (let i = 0; i < text.length; i += 1) {
      const c = text.charCodeAt(i);
      if (c >= 0xD800 && c <= 0xDBFF) {
        const next = text.charCodeAt(i + 1);
        if (!(next >= 0xDC00 && next <= 0xDFFF)) return false;
        i += 1;
      } else if (c >= 0xDC00 && c <= 0xDFFF) return false;
    }
    return true;
  }

  function normalize(value, multiline) {
    const text = value.replace(/\r\n?/g, "\n").trim();
    return multiline ? text : text.replace(/\s+/g, " ");
  }

  function validate(input, kind) {
    const values = {};
    const errors = [];
    getKeys(kind).forEach(function (key) {
      const raw = input && typeof input.get === "function" ? input.get(key) : input && input[key];
      if (raw != null && typeof raw !== "string") {
        values[key] = "";
        errors.push({ field: key, message: FIELDS[key].label + ": isi berupa teks." });
        return;
      }
      const original = raw || "";
      const value = normalize(original, key === "note");
      values[key] = value;
      if (!wellFormed(original) || /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/.test(original)) {
        errors.push({ field: key, message: FIELDS[key].label + ": ada karakter yang tidak dapat dibaca. Ketik ulang bagian tersebut." });
      } else if (value.length > FIELDS[key].maxLength) {
        errors.push({ field: key, message: FIELDS[key].label + ": maksimal " + FIELDS[key].maxLength + " karakter." });
      }
    });
    if (!values.type) {
      errors.push({ field: "type", message: "Pilih kebutuhan; gunakan Lainnya bila belum yakin." });
    } else if (!TYPES.includes(values.type)) {
      errors.push({ field: "type", message: "Pilih kebutuhan dari daftar yang tersedia." });
    }
    if (values.points && !/^[1-9][0-9]{0,5}$/.test(values.points)) {
      errors.push({ field: "points", message: "Jumlah titik: gunakan bilangan bulat 1 sampai 999999, atau kosongkan bila belum tahu." });
    }
    return { ok: errors.length === 0, values: values, errors: errors };
  }

  function messageFor(values, kind) {
    const v = function (key) { return values[key] || "-"; };
    if (kind === "project") return [
      "Halo 3DKan Advertising, saya ingin membahas proyek signage.", "",
      "Perusahaan/Instansi: " + v("company"), "PIC: " + v("pic"),
      "Jenis kebutuhan: " + v("type"), "Jumlah titik: " + v("points"),
      "Lokasi pemasangan: " + v("location"), "Target waktu: " + v("target"),
      "Ringkasan kebutuhan: " + v("note"), "",
      "Mohon dibantu langkah berikutnya untuk verifikasi kebutuhan dan penawaran."
    ].join("\n");
    return [
      "Halo 3DKan Advertising, saya ingin konsultasi proyek signage.", "",
      "Nama/PIC: " + v("name"), "Usaha/Perusahaan: " + v("company"),
      "Kebutuhan: " + v("type"), "Lokasi: " + v("location"),
      "Ukuran perkiraan: " + v("size"), "Jumlah titik: " + v("points"),
      "Catatan: " + v("note"), "",
      "Mohon dibantu verifikasi kebutuhan dan langkah berikutnya untuk penawaran."
    ].join("\n");
  }

  function prepare(input, kind) {
    const result = validate(input, kind);
    if (!result.ok) return result;
    result.message = messageFor(result.values, kind);
    result.url = "https://wa.me/" + RECIPIENT + "?text=" + encodeURIComponent(result.message);
    if (result.url.length > MAX_URL_LENGTH) {
      result.ok = false;
      result.errors.push({ field: "note", message: "Pesan terlalu panjang untuk tautan WhatsApp. Ringkas catatan; detail tambahan dapat dikirim saat chat." });
      delete result.message;
      delete result.url;
    }
    return result;
  }

  function bind(form, kind) {
    getKeys(kind);
    if (form.getAttribute("data-brief-bound") === "true") return;
    const status = form.querySelector("[data-brief-status]");
    const preview = form.querySelector("[data-brief-preview]");
    const link = form.querySelector("[data-brief-whatsapp]");
    const copy = form.querySelector("[data-brief-copy]");
    const compose = form.querySelector("[data-brief-compose]");
    const output = form.querySelector("[data-brief-output]");
    if (!status || !preview || !link || !copy || !compose || !output) return;
    const controls = getKeys(kind).map(function (key) { return form.elements.namedItem(key); });
    if (controls.some(function (field, i) {
      return !field || !["INPUT", "SELECT", "TEXTAREA"].includes(field.tagName) || (getKeys(kind)[i] === "type" && field.tagName !== "SELECT");
    })) return;
    if (preview.tagName !== "TEXTAREA" || link.tagName !== "A" || compose.tagName !== "BUTTON" || copy.tagName !== "BUTTON") return;
    form.setAttribute("data-brief-bound", "true");
    preview.readOnly = true;
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    status.id = status.id || (form.id || "brief-" + kind) + "-status";
    controls.forEach(function (field) {
      const describedBy = (field.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
      if (!describedBy.includes(status.id)) describedBy.push(status.id);
      field.setAttribute("aria-describedby", describedBy.join(" "));
    });
    compose.type = "button";
    copy.type = "button";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    let prepared = null;
    let dirtyAfterPreview = false;
    let copying = false;
    const control = function (key) { return form.elements.namedItem(key); };
    function clearOutput() {
      prepared = null;
      preview.value = "";
      link.removeAttribute("href");
      output.hidden = true;
      copy.disabled = true;
    }
    function clearErrors() {
      getKeys(kind).forEach(function (key) {
        const field = control(key);
        if (field) field.removeAttribute("aria-invalid");
      });
    }
    clearOutput();
    getKeys(kind).forEach(function (key) {
      const field = control(key);
      if (field) {
        if (field.tagName !== "SELECT") field.maxLength = FIELDS[key].maxLength;
        if (key === "type") field.required = true;
        if (key === "points") {
          field.inputMode = "numeric";
          field.pattern = "[1-9][0-9]{0,5}";
        }
      }
    });
    form.noValidate = true;
    function composeMessage(event) {
      event.preventDefault();
      clearOutput();
      clearErrors();
      const result = prepare(new root.FormData(form), kind);
      if (!result.ok) {
        status.textContent = result.errors.map(function (error) { return error.message; }).join(" ");
        result.errors.forEach(function (error) {
          const field = control(error.field);
          if (field) field.setAttribute("aria-invalid", "true");
        });
        const first = control(result.errors[0].field);
        if (first) first.focus();
        return;
      }
      prepared = result;
      dirtyAfterPreview = false;
      preview.value = result.message;
      link.href = result.url;
      copy.disabled = false;
      output.hidden = false;
      status.textContent = "Pesan siap. Periksa isinya, lalu buka WhatsApp dan kirim pesan di sana.";
    }
    form.addEventListener("submit", composeMessage);
    compose.addEventListener("click", function (event) {
      if (compose.type !== "submit") composeMessage(event);
    });
    function edited(event) {
      const wasPrepared = !!prepared;
      if (event.target && event.target.removeAttribute) event.target.removeAttribute("aria-invalid");
      clearOutput();
      if (wasPrepared) dirtyAfterPreview = true;
      status.textContent = dirtyAfterPreview ? "Brief berubah. Susun ulang pesan untuk memakai informasi terbaru." : "";
    }
    form.addEventListener("input", edited);
    form.addEventListener("change", edited);
    link.addEventListener("click", function (event) {
      if (!prepared) event.preventDefault();
    });
    copy.addEventListener("click", async function () {
      if (!prepared || copying) return;
      const current = prepared;
      copying = true;
      try {
        if (!root.navigator || !root.navigator.clipboard || !root.navigator.clipboard.writeText) throw new Error("Clipboard unavailable");
        await root.navigator.clipboard.writeText(current.message);
        if (prepared === current) status.textContent = "Pesan tersalin. Tempelkan di chat WhatsApp untuk mengirim.";
      } catch (error) {
        if (prepared === current) {
          preview.focus();
          preview.select();
          status.textContent = "Salin pesan yang dipilih melalui menu perangkat atau Ctrl+C, lalu tempelkan di WhatsApp.";
        }
      } finally {
        copying = false;
      }
    });
    form.querySelectorAll("fieldset[data-brief-fields]").forEach(function (fieldset) { fieldset.disabled = false; });
    compose.disabled = false;
  }

  return Object.freeze({ RECIPIENT: RECIPIENT, MAX_URL_LENGTH: MAX_URL_LENGTH, TYPES: TYPES, FIELDS: FIELDS, validate: validate, prepare: prepare, bind: bind });
});
