(function () {
  "use strict";
  const root = document.getElementById("cutting-app");
  if (!root) return;
  const texts = JSON.parse(document.getElementById("cutting-texts").textContent);
  const t = (key, values = {}) => Object.entries(values).reduce((s, [k, v]) => s.replaceAll(`{${k}}`, String(v)), texts[key] || texts["error.unexpected"]);
  const $ = (id) => document.getElementById(id);
  const ids = ["product", "market", "color"];
  const UNIQLO_CUSTOMER = "UNIQLO";
  const controls = Object.fromEntries(ids.map((id) => [id, $(id)]));
  const pickerTriggers = Object.fromEntries(ids.map((id) => [id, $(`${id}-picker`)]));
  const pickerLabels = Object.fromEntries(ids.map((id) => [id, $(`${id}-picker-label`)]));
  const pickerTitles = { product: "ui.choose_product", market: "ui.choose_market", color: "ui.choose_color" };
  const pickerDialog = $("entry-picker-dialog");
  const pickerGrid = $("entry-picker-grid");
  const pickerEmpty = $("entry-picker-empty");
  const pickerClose = $("entry-picker-close");
  let activePicker = "";
  let pickerRestoreTarget;
  let autoFullscreenAttempted = false;
  let focusedInputScrollFrame = 0;
  const filters = {
    product: $("filter-product"), color: $("filter-color"), market: $("filter-market"),
    from: $("filter-from"), to: $("filter-to"), identifier: $("filter-identifier"),
  };
  const core = window.CuttingQueue;
  let deviceId = "";
  try { deviceId = localStorage.getItem("cutting.device") || ""; }
  catch (_) { frappe.show_alert({ message: t("ui.storage_error"), indicator: "red" }, 7); return; }
  let cache = {};
  let editing = null;
  let inFlight = false;
  let deviceBusy = false;
  let storageReady = true;
  let connected = navigator.onLine;
  let pageSize = 8;
  let currentPage = 1;
  let qrStream = null;
  let qrFrame = 0;
  let qrSession = 0;
  const stateKey = () => `cutting.queue.${deviceId}`;
  const cacheKey = () => `cutting.catalog.${deviceId}`;
  const nowUtc = () => Date.now() + (cache.clock_delta_ms || 0);
  document.documentElement.lang = root.dataset.lang;
  const deviceSettingsDialog = $("device-settings-dialog");
  const deviceCacheConfirmDialog = $("device-cache-confirm-dialog");
  $("device-settings-body").append($("device-settings-template").content.cloneNode(true));
  deviceSettingsDialog.addEventListener("close", () => {
    stopQrScanner();
    $("open-device-settings").setAttribute("aria-expanded", "false");
    $("open-device-settings").focus();
  });
  deviceCacheConfirmDialog.addEventListener("close", () => {
    if (deviceSettingsDialog.open) $("clear-device-cache").focus();
    else $("open-device-settings").focus();
  });

  function closeDeviceSettings() {
    if (deviceSettingsDialog.open) deviceSettingsDialog.close();
  }

  function openDeviceSettings(focusId = true) {
    $("device-id").value = deviceId;
    if (!deviceSettingsDialog.open) deviceSettingsDialog.showModal();
    $("open-device-settings").setAttribute("aria-expanded", "true");
    if (focusId) $("device-id").focus();
  }

  function stopQrScanner() {
    qrSession += 1;
    if (qrFrame) cancelAnimationFrame(qrFrame);
    qrFrame = 0;
    if (qrStream) qrStream.getTracks().forEach((track) => track.stop());
    qrStream = null;
    $("qr-video").pause();
    $("qr-video").srcObject = null;
    $("camera-status").textContent = t("ui.camera_idle");
  }

  async function scanQr() {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      $("camera-status").textContent = t("ui.camera_insecure");
      notice(t("ui.camera_insecure"), true);
      return;
    }
    if (!window.BarcodeDetector) {
      $("camera-status").textContent = t("ui.camera_unsupported");
      notice(t("ui.camera_unsupported"), true);
      return;
    }
    const session = ++qrSession;
    try {
      const detector = new BarcodeDetector({ formats: ["qr_code"] });
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
      if (session !== qrSession) { stream.getTracks().forEach((track) => track.stop()); return; }
      qrStream = stream;
      const video = $("qr-video");
      video.srcObject = qrStream;
      await video.play();
      $("camera-status").textContent = t("ui.camera_scanning");
      const detect = async () => {
        if (!qrStream || session !== qrSession) return;
        try {
          const codes = await detector.detect(video);
          if (codes.length) {
            const id = window.CuttingDevice.parseId(codes[0].rawValue);
            stopQrScanner();
            if (!id) { notice(t("ui.device_id_invalid"), true); return; }
            $("device-id").value = id;
            $("device-id").focus();
            notice(t("ui.qr_read"));
            return;
          }
        } catch (_) { stopQrScanner(); notice(t("ui.camera_failed"), true); return; }
        if (session === qrSession) qrFrame = requestAnimationFrame(detect);
      };
      qrFrame = requestAnimationFrame(detect);
    } catch (_) {
      stopQrScanner();
      $("camera-status").textContent = t("ui.camera_failed");
      notice(t("ui.camera_failed"), true);
    }
  }

  function activateDevice() {
    const raw = $("device-id").value.trim();
    if (!raw) { notice(t("ui.device_required"), true); return; }
    const candidate = window.CuttingDevice.parseId(raw);
    if (!candidate) { notice(t("ui.device_id_invalid"), true); return; }
    deviceAction(true, candidate);
  }

  function clearDeviceCache() {
    if (deviceBusy || inFlight) return;
    deviceCacheConfirmDialog.showModal();
    $("cancel-device-cache").focus();
  }

  function confirmClearDeviceCache() {
    if (!deviceCacheConfirmDialog.open) return;
    deviceCacheConfirmDialog.close();
    try {
      window.CuttingDevice.clearStorage(localStorage);
      stopQrScanner();
      deviceId = "";
      cache = {};
      editing = null;
      storageReady = true;
      $("device-id").value = "";
      $("entry-form").reset();
      renderSelectors();
      render();
      closeDeviceSettings();
      notice(t("ui.device_cache_cleared"));
    } catch (_) { notice(t("ui.storage_error"), true); }
  }

  function closeDeviceCacheConfirmation() {
    if (deviceCacheConfirmDialog.open) deviceCacheConfirmDialog.close();
  }

  function updateFullscreenButton() {
    const active = document.fullscreenElement === root;
    $("fullscreen-enter-icon").hidden = active;
    $("fullscreen-exit-icon").hidden = !active;
    const text = t(active ? "ui.exit_fullscreen" : "ui.fullscreen");
    $("fullscreen-button").setAttribute("aria-label", text);
    $("fullscreen-button").title = text;
  }

  function autoFullscreenOnInteraction(event) {
    if (!event.isTrusted || autoFullscreenAttempted || document.fullscreenElement) return;
    if (event.target instanceof Element && event.target.closest("#fullscreen-button")) return;
    autoFullscreenAttempted = true;
    try { root.requestFullscreen().catch(() => notice(t("ui.fullscreen_failed"), true)); }
    catch (_) { notice(t("ui.fullscreen_failed"), true); }
  }

  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await root.requestFullscreen();
    } catch (_) { notice(t("ui.fullscreen_failed"), true); }
  }

  function keepFocusedEntryInputVisible() {
    const input = document.activeElement;
    const isEntryInput = input instanceof HTMLElement && ["identifier", "quantity"].includes(input.id);
    root.classList.toggle("cutting-entry-input-focused", document.fullscreenElement === root && isEntryInput);
    if (!isEntryInput) {
      cancelAnimationFrame(focusedInputScrollFrame);
      return;
    }
    cancelAnimationFrame(focusedInputScrollFrame);
    focusedInputScrollFrame = requestAnimationFrame(() => {
      const viewport = window.visualViewport;
      const viewportTop = viewport?.offsetTop || 0;
      const viewportBottom = viewportTop + (viewport?.height || window.innerHeight);
      const bounds = input.getBoundingClientRect();
      const margin = 16;
      if (bounds.top < viewportTop + margin || bounds.bottom > viewportBottom - margin) {
        input.scrollIntoView({ block: "center", inline: "nearest" });
      }
    });
  }

  async function checkConnection() {
    try {
      if (!navigator.onLine) throw new Error(t("ui.offline"));
      await request("cutting.api.device_epoch");
      connected = true;
      render();
      notice(t("ui.online"));
      if (deviceId) await deviceAction(false);
    } catch (error) {
      connected = false;
      render();
      notice(error.message || t("ui.sync_failed"), true);
    }
  }

  function notice(text, error = false) {
    if (text) frappe.show_alert({ message: text, indicator: error ? "red" : "green" }, error ? 7 : 4);
  }

  function readState() {
    try {
      const value = localStorage.getItem(stateKey());
      const state = value ? JSON.parse(value) : core.empty();
      if (![state.records, state.updates, state.deletes, state.saved].every(Array.isArray)) throw new Error();
      return state;
    } catch (_) { storageReady = false; throw new Error(t("ui.storage_error")); }
  }

  function persist(state) {
    try { localStorage.setItem(stateKey(), JSON.stringify(state)); }
    catch (_) { throw new Error(t("ui.storage_error")); }
  }

  function loadCache() {
    cache = JSON.parse(localStorage.getItem(cacheKey()) || "{}");
    renderSelectors();
    render();
  }

  function uuid() {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    const hex = [...bytes].map((v) => v.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  function errorText(payload) {
    try {
      const messages = JSON.parse(payload._server_messages || "[]");
      const item = JSON.parse(messages[0] || "{}");
      if (item.message) return new DOMParser().parseFromString(item.message, "text/html").body.textContent;
    } catch (_) { /* The catalog supplies the fallback. */ }
    return t("error.unexpected");
  }

  async function request(method, args = {}, post = false, headers = {}) {
    const query = new URLSearchParams(Object.entries(args).map(([key, value]) => [key, typeof value === "object" ? JSON.stringify(value) : value]));
    let response;
    try {
      response = await fetch(`/api/method/${method}${post ? "" : `?${query}`}`, {
        method: post ? "POST" : "GET", credentials: "omit", cache: "no-store",
        headers: { "Content-Type": "application/json", "Accept-Language": root.dataset.lang, ...headers },
        ...(post ? { body: JSON.stringify(args) } : {}),
      });
    } catch (_) { connected = false; throw new Error(t("ui.sync_failed")); }
    connected = true;
    const payload = await response.json();
    if (!response.ok || payload.exc_type) {
      const error = new Error(errorText(payload)); error.status = response.status; throw error;
    }
    return payload.message;
  }

  async function sharedDevice(method, args) {
    const epoch = await request("cutting.api.device_epoch");
    return request(`cutting.api.${method}`, args, true, { "X-Factory-Data-Epoch": epoch.generation || "" });
  }

  async function deviceAction(activate, candidate = deviceId) {
    if (deviceBusy || inFlight) return;
    deviceBusy = true;
    try {
      if (!candidate) throw new Error(t("ui.device_required"));
      const response = await sharedDevice(activate ? "register_device" : "check_device", { id: candidate });
      const device = response.device || response;
      const data = await request("cutting.api.bootstrap", { id: candidate });
      const nextCache = { ...data, approved: true, device_name: device.device_name,
        clock_delta_ms: Date.parse(data.server_now_utc) - Date.now() };
      localStorage.setItem(`cutting.catalog.${candidate}`, JSON.stringify(nextCache));
      if (candidate !== deviceId) {
        localStorage.setItem("cutting.device", candidate);
        deviceId = candidate;
        editing = null;
        storageReady = true;
      }
      cache = nextCache;
      renderSelectors();
      render();
      await syncQueue();
      const rows = await request("cutting.api.get_device_records", { id: deviceId });
      persist(core.mergeServer(readState(), rows));
      if (activate) { closeDeviceSettings(); notice(response.notice || t("ok.device_activated")); }
    } catch (error) {
      if (candidate === deviceId && error.status && [400, 403, 404].includes(error.status)) {
        cache.approved = false;
        localStorage.setItem(cacheKey(), JSON.stringify(cache));
      }
      if (activate || candidate === deviceId) notice(error.message, true);
    } finally { deviceBusy = false; render(); }
  }

  function options(select, rows, selected = select.value, placeholder = t("ui.select"), includeName = true) {
    select.replaceChildren(new Option(placeholder, ""));
    for (const row of rows) {
      const label = includeName ? [row.code, row.name].filter(Boolean).join(" — ") : row.code || row.id;
      const option = new Option(label, row.id);
      option.dataset.code = row.code || row.name || row.id;
      option.dataset.name = row.name || "";
      select.add(option);
    }
    if (rows.some((row) => row.id === selected)) select.value = selected;
  }

  function updatePickerLabels() {
    for (const id of ids) {
      const select = controls[id];
      const option = select.selectedOptions[0];
      pickerLabels[id].textContent = select.value && option ? pickerText(id, option) : t(pickerTitles[id]);
    }
    pickerTriggers.market.disabled = !controls.product.value;
    pickerTriggers.color.disabled = !controls.product.value || !controls.market.value;
  }

  function pickerText(kind, option) {
    const code = option.dataset.code || option.value;
    const name = option.dataset.name;
    return kind === "product" || !name || name === code ? code : `${code} - ${name}`;
  }

  function renderSelectors() {
    const catalog = cache.catalog || {};
    const variants = catalog.product_variants || [];
    const uniqloCustomerIds = new Set((catalog.customers || [])
      .filter((customer) => [customer.code, customer.name]
        .some((value) => String(value || "").trim().toUpperCase() === UNIQLO_CUSTOMER))
      .map((customer) => customer.id));
    const products = (catalog.products || []).filter((row) => uniqloCustomerIds.has(row.customer_id)
      && variants.some((v) => v.product === row.id));
    options(controls.product, products);
    const choices = variants.filter((row) => row.product === controls.product.value);
    options(controls.market, (catalog.markets || []).filter((row) => choices.some((v) => v.market === row.id)));
    options(controls.color, (catalog.colors || []).filter((row) => controls.market.value && choices.some((v) => v.color === row.id && v.market === controls.market.value)));
    controls.market.disabled = !controls.product.value;
    controls.color.disabled = !controls.product.value || !controls.market.value;
    updatePickerLabels();
  }

  function renderPickerOptions(kind) {
    const select = controls[kind];
    const options = [...select.options].slice(1);
    pickerGrid.replaceChildren();
    pickerEmpty.hidden = options.length > 0;
    for (const option of options) {
      const card = document.createElement("button");
      card.type = "button";
      const selected = option.value === select.value;
      card.className = `btn btn-default cutting-picker-card${kind !== "product" ? " cutting-picker-card-inline" : ""}${selected ? " cutting-picker-card-selected" : ""}`;
      card.setAttribute("aria-pressed", String(selected));
      if (kind === "product") {
        const code = document.createElement("span");
        code.className = "cutting-picker-card-code";
        code.textContent = option.dataset.code || option.textContent;
        card.append(code);
      } else {
        const label = document.createElement("span");
        label.textContent = pickerText(kind, option);
        card.append(label);
      }
      card.addEventListener("click", () => {
        const chosen = activePicker;
        select.value = option.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        pickerTriggers[chosen].setAttribute("aria-expanded", "false");
        const next = { product: "market", market: "color", color: "" }[chosen];
        pickerRestoreTarget = next ? null : $("identifier");
        pickerDialog.close();
        if (next) openPicker(next);
        else $("identifier").focus();
      });
      pickerGrid.append(card);
    }
  }

  function openPicker(kind) {
    const trigger = pickerTriggers[kind];
    if (!trigger || trigger.matches(":disabled")) return;
    activePicker = kind;
    pickerRestoreTarget = trigger;
    $("entry-picker-title").textContent = t(pickerTitles[kind]);
    renderPickerOptions(kind);
    trigger.setAttribute("aria-expanded", "true");
    pickerDialog.showModal();
    (pickerGrid.querySelector('[aria-pressed="true"]') || pickerGrid.querySelector("button") || pickerClose).focus();
  }

  function restorePickerFocus() {
    if (pickerDialog.open) return;
    const target = pickerRestoreTarget;
    pickerRestoreTarget = undefined;
    if (!target) return;
    if (activePicker) pickerTriggers[activePicker].setAttribute("aria-expanded", "false");
    activePicker = "";
    target.focus();
  }

  for (const id of ids) pickerTriggers[id].addEventListener("click", () => openPicker(id));
  pickerClose.addEventListener("click", () => pickerDialog.close());
  pickerDialog.addEventListener("click", (event) => { if (event.target === pickerDialog) pickerDialog.close(); });
  pickerDialog.addEventListener("close", restorePickerFocus);

  function renderFilterOptions(savedRows) {
    const catalog = cache.catalog || {};
    const values = {
      product: new Set(savedRows.map((row) => row.product).filter(Boolean)),
      color: new Set(savedRows.map((row) => row.color).filter(Boolean)),
      market: new Set(savedRows.map((row) => row.market).filter(Boolean)),
    };
    const rowsFor = (type, ids) => {
      const known = (catalog[type] || []).filter((row) => ids.has(row.id));
      const knownIds = new Set(known.map((row) => row.id));
      const missing = [...ids].filter((id) => !knownIds.has(id))
        .sort((left, right) => String(left).localeCompare(String(right), undefined, { numeric: true, sensitivity: "base" }))
        .map((id) => ({ id, code: id }));
      return [...known, ...missing];
    };
    options(filters.product, rowsFor("products", values.product), filters.product.value, t("ui.all_products"), false);
    options(filters.color, rowsFor("colors", values.color), filters.color.value, t("ui.all_colors"));
    options(filters.market, rowsFor("markets", values.market), filters.market.value, t("ui.all_markets"));
  }

  function siteDateKey(value) {
    return core.siteDateKey(value, cache.server_utc_offset_minutes || 0);
  }

  function siteTodayKey() {
    return siteDateKey(new Date(nowUtc()).toISOString());
  }

  function filteredRows(rows) {
    const product = filters.product.value;
    const color = filters.color.value;
    const market = filters.market.value;
    const from = filters.from.value;
    const to = filters.to.value;
    const identifier = filters.identifier.value.trim().toLocaleLowerCase();
    return rows.filter((row) => {
      const day = siteDateKey(row.occurred_at);
      return (!product || row.product === product)
        && (!color || row.color === color)
        && (!market || row.market === market)
        && (!from || day >= from)
        && (!to || day <= to)
        && (!identifier || String(row.product_code_identifier || "").toLocaleLowerCase().includes(identifier));
    });
  }

  function label(type, id) {
    const row = (cache.catalog?.[type] || []).find((item) => item.id === id);
    return row ? row.code || row.name : id || "";
  }

  function render() {
    let state;
    try { state = readState(); }
    catch (error) { $("entry-fields").disabled = true; $("sync").disabled = true; notice(error.message, true); return; }
    for (const input of [filters.from, filters.to]) input.closest(".cutting-date-filter").classList.toggle("has-value", Boolean(input.value));
    const count = state.records.length + state.updates.length + state.deletes.length;
    $("pending-count").textContent = t("ui.pending_count", { count });
    $("entry-fields").disabled = deviceBusy || !cache.approved || !cache.catalog;
    $("device-settings-status").textContent = cache.approved ? t("ui.approved") : t("ui.pending");
    $("device-settings-status").className = `indicator-pill ${cache.approved ? "green" : "orange"}`;
    $("saved-device-id").value = deviceId;
    $("device-name").value = cache.device_name || "";
    $("device-id").disabled = inFlight || deviceBusy;
    $("activate-device").disabled = inFlight || deviceBusy;
    $("scan-qr").disabled = inFlight || deviceBusy;
    $("clear-device-cache").disabled = inFlight || deviceBusy;
    $("sync").disabled = inFlight || !cache.approved || !count;
    const connectionText = connected ? t("ui.online") : t("ui.offline");
    $("connection-status").textContent = connectionText;
    $("network-button").className = `btn btn-default btn-sm mr-1 ${connected ? "text-success" : "text-muted"}`;
    $("network-button").setAttribute("aria-label", connectionText);
    $("network-button").title = connectionText;
    const rows = state.saved.slice().sort((a, b) => String(b.occurred_at).localeCompare(String(a.occurred_at)));
    renderFilterOptions(rows);
    const matched = filteredRows(rows);
    const pageCount = Math.max(1, Math.ceil(matched.length / pageSize));
    currentPage = Math.min(currentPage, pageCount);
    const pageRows = matched.slice((currentPage - 1) * pageSize, currentPage * pageSize);
    $("records-count").textContent = String(matched.length);
    $("records-count").setAttribute("aria-label", t("ui.saved_count", { count: matched.length }));
    $("page-size-label").textContent = t("ui.page_size", { count: pageSize });
    $("page-label").textContent = t("ui.page", { current: currentPage, total: pageCount });
    $("page-size-down").disabled = pageSize <= 5;
    $("page-size-up").disabled = pageSize >= 50;
    $("previous-page").disabled = currentPage <= 1;
    $("next-page").disabled = currentPage >= pageCount;
    $("records-body").replaceChildren();
    const todayKey = siteTodayKey();
    for (const row of pageRows) {
      const tr = document.createElement("tr");
      const occurred = String(row.occurred_at).replace(" ", "T");
      const date = new Date(occurred + (/Z$|[+-]\d\d:\d\d$/.test(occurred) ? "" : "Z"));
      const siteDate = new Date(date.getTime() + (cache.server_utc_offset_minutes || 0) * 60000);
      const values = [siteDate.toLocaleString(root.dataset.lang === "en" ? "en-US" : "vi-VN", { timeZone: "UTC" }), label("products", row.product), label("markets", row.market), label("colors", row.color), row.product_code_identifier, row.quantity, row.synced ? t("ui.synced") : t("ui.pending_sync")];
      for (const value of values) { const td = document.createElement("td"); td.textContent = value; tr.append(td); }
      const actions = document.createElement("td");
      const actionGroup = document.createElement("div"); actionGroup.className = "cutting-record-actions";
      const editableToday = siteDateKey(row.occurred_at) === todayKey;
      for (const [key, handler] of [["ui.edit", () => editRecord(row)], ["ui.delete", () => deleteRecord(row)]]) {
        const editBlocked = key === "ui.edit" && !editableToday;
        const buttonText = editBlocked ? t("error.edit_today_only") : t(key);
        const button = document.createElement("button"); button.type = "button"; button.className = "btn btn-sm " + (key === "ui.delete" ? "cutting-record-delete" : "cutting-record-edit"); button.setAttribute("aria-label", buttonText); button.title = buttonText; button.disabled = inFlight || editBlocked;
        const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg"); icon.setAttribute("viewBox", "0 0 24 24"); icon.setAttribute("aria-hidden", "true");
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path"); path.setAttribute("d", key === "ui.delete" ? "M4 7h16M10 11v6m4-6v6M6 7l1 14h10l1-14M9 7V4h6v3" : "M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"); icon.append(path); button.append(icon);
        button.addEventListener("click", handler); actionGroup.append(button);
      }
      actions.append(actionGroup); tr.append(actions); $("records-body").append(tr);
    }
    $("empty-records").textContent = rows.length ? t("ui.no_filtered_records") : t("ui.no_records");
    $("empty-records").hidden = pageRows.length > 0;
  }

  function editRecord(row) {
    if (siteDateKey(row.occurred_at) !== siteTodayKey()) { notice(t("error.edit_today_only"), true); return; }
    editing = row;
    renderSelectors(); controls.product.value = row.product;
    renderSelectors(); controls.market.value = row.market;
    renderSelectors(); controls.color.value = row.color;
    renderSelectors();
    $("identifier").value = row.product_code_identifier;
    $("quantity").value = row.quantity;
    $("cancel-edit").hidden = false;
    $("quantity").focus();
  }

  function cancelEdit() { editing = null; $("cancel-edit").hidden = true; $("quantity").value = ""; }

  function deleteRecord(row) {
    if (!confirm(t("ui.confirm_delete"))) return;
    try { const state = readState(); core.remove(state, row.local_event_id); persist(state); render(); syncQueue(); }
    catch (error) { notice(error.message, true); }
  }

  async function syncQueue() {
    if (inFlight || !storageReady || !cache.approved || !deviceId) return;
    let state = readState();
    const expiredUpdates = state.updates.filter((row) => siteDateKey(row.occurred_at) !== siteTodayKey());
    if (expiredUpdates.length) {
      inFlight = true; render();
      try {
        const rows = await request("cutting.api.get_device_records", { id: deviceId });
        state = readState();
        const expiredIds = state.updates
          .filter((row) => siteDateKey(row.occurred_at) !== siteTodayKey())
          .map((row) => row.local_event_id);
        if (expiredIds.length) {
          core.discardUpdates(state, expiredIds);
          notice(t("ui.expired_edits_discarded", { count: expiredIds.length }), true);
        }
        persist(core.mergeServer(state, rows));
      } catch (error) {
        notice(error.message || t("ui.sync_failed"), true);
        return;
      } finally { inFlight = false; render(); }
    }
    state = readState();
    if (!state.records.length && !state.updates.length && !state.deletes.length) return;
    const sent = { records: state.records.slice(0, 200), updates: state.updates.slice(0, 200), deletes: state.deletes.slice(0, 100) };
    inFlight = true; render();
    try {
      const result = await request("cutting.api.sync_records", { id: deviceId, ...sent }, true);
      persist(core.acknowledge(readState(), sent, result));
      notice(t("ui.synced"));
    } catch (error) { notice(error.message || t("ui.sync_failed"), true); }
    finally { inFlight = false; render(); }
  }

  $("entry-form").addEventListener("submit", (event) => {
    event.preventDefault();
    try {
      if (!cache.approved) throw new Error(t("ui.pending"));
      if (editing && siteDateKey(editing.occurred_at) !== siteTodayKey()) {
        cancelEdit();
        throw new Error(t("error.edit_today_only"));
      }
      const product = controls.product.value, market = controls.market.value, color = controls.color.value;
      if (!(cache.catalog.product_variants || []).some((row) => row.product === product && row.market === market && row.color === color)) throw new Error(t("ui.invalid_selection"));
      const quantity = Number($("quantity").value);
      if (!Number.isSafeInteger(quantity) || quantity <= 0 || quantity > 2147483647) throw new Error(t("error.quantity"));
      const identifier = $("identifier").value.trim();
      if (!identifier || identifier.length > 100) throw new Error(t("error.identifier"));
      const item = { local_event_id: editing?.local_event_id || uuid(), product, color, market, product_code_identifier: identifier, quantity, occurred_at: editing?.occurred_at || new Date(nowUtc()).toISOString() };
      const state = readState(); (editing ? core.edit : core.add)(state, item); persist(state);
      cancelEdit(); notice(t("ui.saved")); render(); syncQueue();
    } catch (error) { notice(error.message, true); }
  });
  for (const id of ids) controls[id].addEventListener("change", renderSelectors);
  for (const control of Object.values(filters)) {
    control.addEventListener(control === filters.identifier ? "input" : "change", () => { currentPage = 1; render(); });
  }
  $("clear-filters").addEventListener("click", () => {
    for (const control of Object.values(filters)) control.value = "";
    currentPage = 1;
    render();
  });
  $("new-entry").addEventListener("click", () => {
    $("entry-form").reset();
    editing = null;
    $("cancel-edit").hidden = true;
    renderSelectors();
    if (!$("entry-fields").disabled) pickerTriggers.product.focus();
  });
  $("page-size-down").addEventListener("click", () => { pageSize = Math.max(5, pageSize - 5); currentPage = 1; render(); });
  $("page-size-up").addEventListener("click", () => { pageSize = Math.min(50, pageSize + 5); currentPage = 1; render(); });
  $("previous-page").addEventListener("click", () => { currentPage = Math.max(1, currentPage - 1); render(); });
  $("next-page").addEventListener("click", () => { currentPage += 1; render(); });
  $("fullscreen-button").addEventListener("click", toggleFullscreen);
  root.addEventListener("click", autoFullscreenOnInteraction, true);
  root.addEventListener("keydown", autoFullscreenOnInteraction, true);
  document.addEventListener("fullscreenchange", updateFullscreenButton);
  $("device-settings-close").addEventListener("click", closeDeviceSettings);
  deviceSettingsDialog.addEventListener("click", (event) => {
    if (event.target === deviceSettingsDialog) closeDeviceSettings();
  });
  $("close-device-cache-confirm").addEventListener("click", closeDeviceCacheConfirmation);
  $("cancel-device-cache").addEventListener("click", closeDeviceCacheConfirmation);
  $("confirm-device-cache").addEventListener("click", confirmClearDeviceCache);
  deviceCacheConfirmDialog.addEventListener("click", (event) => {
    if (event.target === deviceCacheConfirmDialog) closeDeviceCacheConfirmation();
  });
  root.addEventListener("focusin", keepFocusedEntryInputVisible);
  root.addEventListener("focusout", () => requestAnimationFrame(keepFocusedEntryInputVisible));
  window.visualViewport?.addEventListener("resize", keepFocusedEntryInputVisible);
  window.visualViewport?.addEventListener("scroll", keepFocusedEntryInputVisible);
  $("network-button").addEventListener("click", checkConnection);
  $("open-device-settings").addEventListener("click", () => openDeviceSettings());
  $("scan-qr").addEventListener("click", scanQr);
  $("activate-device").addEventListener("click", activateDevice);
  $("device-id").addEventListener("keydown", (event) => { if (event.key === "Enter") activateDevice(); });
  $("clear-device-cache").addEventListener("click", clearDeviceCache);
  $("sync").addEventListener("click", syncQueue);
  $("cancel-edit").addEventListener("click", cancelEdit);
  window.addEventListener("online", () => { connected = true; render(); if (deviceId) deviceAction(false); });
  window.addEventListener("offline", () => { connected = false; render(); });
  window.addEventListener("storage", (event) => { if (event.key === stateKey()) render(); });
  setInterval(() => { if (navigator.onLine) syncQueue(); }, 15000);
  try {
    loadCache();
    if (deviceId && navigator.onLine) deviceAction(false);
    else if (!deviceId) openDeviceSettings(false);
  }
  catch (error) {
    $("entry-fields").disabled = true;
    notice(error.message === t("ui.storage_error") ? error.message : t("error.unexpected"), true);
  }
})();
