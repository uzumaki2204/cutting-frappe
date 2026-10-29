(function () {
  "use strict";
  const root = document.getElementById("cutting-app");
  if (!root) return;
  const texts = JSON.parse(document.getElementById("cutting-texts").textContent);
  const t = (key, values = {}) => Object.entries(values).reduce((s, [k, v]) => s.replaceAll(`{${k}}`, String(v)), texts[key] || texts["error.unexpected"]);
  const $ = (id) => document.getElementById(id);
  const ids = ["product", "market", "color"];
  const controls = Object.fromEntries(ids.map((id) => [id, $(id)]));
  const filters = {
    product: $("filter-product"), color: $("filter-color"), market: $("filter-market"),
    from: $("filter-from"), to: $("filter-to"), identifier: $("filter-identifier"),
  };
  const core = window.CuttingQueue;
  let deviceId = "";
  try { deviceId = localStorage.getItem("cutting.device") || ""; }
  catch (_) { $("notice").textContent = t("ui.storage_error"); $("notice").hidden = false; return; }
  let cache = {};
  let editing = null;
  let inFlight = false;
  let deviceBusy = false;
  let storageReady = true;
  let connected = navigator.onLine;
  let pageSize = 8;
  let currentPage = 1;
  const stateKey = () => `cutting.queue.${deviceId}`;
  const cacheKey = () => `cutting.catalog.${deviceId}`;
  const nowUtc = () => Date.now() + (cache.clock_delta_ms || 0);
  document.documentElement.lang = root.dataset.lang;
  $("device-id").value = deviceId;
  const deviceSettings = $("device-settings");

  function closeDeviceSettings() {
    if (deviceSettings.open) deviceSettings.close();
    $("open-device-settings").setAttribute("aria-expanded", "false");
    $("open-device-settings").focus();
  }

  function updateFullscreenButton() {
    const active = document.fullscreenElement === root;
    $("fullscreen-enter-icon").hidden = active;
    $("fullscreen-exit-icon").hidden = !active;
    const text = t(active ? "ui.exit_fullscreen" : "ui.fullscreen");
    $("fullscreen-button").setAttribute("aria-label", text);
    $("fullscreen-button").title = text;
  }

  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await root.requestFullscreen();
    } catch (_) { notice(t("ui.fullscreen_failed"), true); }
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
    $("notice").textContent = text;
    $("notice").className = `alert ${error ? "alert-danger" : "alert-info"}`;
    $("notice").hidden = !text;
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
    renderFilterOptions();
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

  function setDevice() {
    const value = $("device-id").value.trim().toLowerCase();
    if (!value) throw new Error(t("ui.device_required"));
    if (value !== deviceId) {
      deviceId = value;
      storageReady = true;
      localStorage.setItem("cutting.device", deviceId);
      editing = null;
      loadCache();
    }
  }

  async function deviceAction(register) {
    if (deviceBusy || inFlight) return;
    deviceBusy = true;
    try {
      if (register && !$("device-id").value.trim()) $("device-id").value = uuid();
      setDevice();
      notice(t("ui.loading"));
      const response = await sharedDevice(register ? "register_device" : "check_device", { id: deviceId, device_name: t("ui.title") });
      const device = response.device || response;
      cache.approved = device.status === "Approved" && device.is_active && Boolean(device.company);
      localStorage.setItem(cacheKey(), JSON.stringify(cache));
      if (cache.approved) {
        const data = await request("cutting.api.bootstrap", { id: deviceId });
        cache = { ...data, approved: true, clock_delta_ms: Date.parse(data.server_now_utc) - Date.now() };
        localStorage.setItem(cacheKey(), JSON.stringify(cache));
        renderSelectors();
        renderFilterOptions();
        await syncQueue();
        const rows = await request("cutting.api.get_device_records", { id: deviceId });
        persist(core.mergeServer(readState(), rows));
        closeDeviceSettings();
      }
      notice(response.notice || (cache.approved ? t("ui.approved") : t("ui.pending")));
    } catch (error) {
      if (error.status && [400, 403, 404].includes(error.status)) {
        cache.approved = false;
        localStorage.setItem(cacheKey(), JSON.stringify(cache));
      }
      notice(error.message, true);
    } finally { deviceBusy = false; render(); }
  }

  function options(select, rows, selected = select.value, placeholder = t("ui.select")) {
    select.replaceChildren(new Option(placeholder, ""));
    for (const row of rows) select.add(new Option([row.code, row.name].filter(Boolean).join(" — "), row.id));
    if (rows.some((row) => row.id === selected)) select.value = selected;
  }

  function renderSelectors() {
    const catalog = cache.catalog || {};
    const variants = catalog.product_variants || [];
    const products = (catalog.products || []).filter((row) => variants.some((v) => v.product === row.id));
    options(controls.product, products);
    const choices = variants.filter((row) => row.product === controls.product.value);
    options(controls.market, (catalog.markets || []).filter((row) => choices.some((v) => v.market === row.id)));
    options(controls.color, (catalog.colors || []).filter((row) => choices.some((v) => v.color === row.id && (!controls.market.value || v.market === controls.market.value))));
  }

  function renderFilterOptions() {
    const catalog = cache.catalog || {};
    options(filters.product, catalog.products || [], filters.product.value, t("ui.all_products"));
    options(filters.color, catalog.colors || [], filters.color.value, t("ui.all_colors"));
    options(filters.market, catalog.markets || [], filters.market.value, t("ui.all_markets"));
  }

  function siteDateKey(value) {
    const iso = String(value || "").replace(" ", "T");
    const date = new Date(iso + (/Z$|[+-]\d\d:\d\d$/.test(iso) ? "" : "Z"));
    if (!Number.isFinite(date.getTime())) return "";
    return new Date(date.getTime() + (cache.server_utc_offset_minutes || 0) * 60000).toISOString().slice(0, 10);
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
    const count = state.records.length + state.updates.length + state.deletes.length;
    $("pending-count").textContent = t("ui.pending_count", { count });
    $("entry-fields").disabled = deviceBusy || !cache.approved || !cache.catalog;
    $("device-settings-status").textContent = cache.approved ? t("ui.approved") : t("ui.pending");
    $("device-settings-status").className = `indicator-pill ${cache.approved ? "green" : "orange"}`;
    $("device-id").disabled = inFlight || deviceBusy;
    $("register-device").disabled = inFlight || deviceBusy;
    $("check-device").disabled = inFlight || deviceBusy;
    $("sync").disabled = inFlight || !cache.approved || !count;
    const connectionText = connected ? t("ui.online") : t("ui.offline");
    $("connection-status").textContent = connectionText;
    $("network-button").className = `btn btn-default btn-sm mr-1 ${connected ? "text-success" : "text-muted"}`;
    $("network-button").setAttribute("aria-label", connectionText);
    $("network-button").title = connectionText;
    const rows = state.saved.slice().sort((a, b) => String(b.occurred_at).localeCompare(String(a.occurred_at)));
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
    for (const row of pageRows) {
      const tr = document.createElement("tr");
      const occurred = String(row.occurred_at).replace(" ", "T");
      const date = new Date(occurred + (/Z$|[+-]\d\d:\d\d$/.test(occurred) ? "" : "Z"));
      const siteDate = new Date(date.getTime() + (cache.server_utc_offset_minutes || 0) * 60000);
      const values = [siteDate.toLocaleString(root.dataset.lang === "en" ? "en-US" : "vi-VN", { timeZone: "UTC" }), label("products", row.product), label("markets", row.market), label("colors", row.color), row.product_code_identifier, row.quantity, row.synced ? t("ui.synced") : t("ui.pending_sync")];
      for (const value of values) { const td = document.createElement("td"); td.textContent = value; tr.append(td); }
      const actions = document.createElement("td");
      for (const [key, handler] of [["ui.edit", () => editRecord(row)], ["ui.delete", () => deleteRecord(row)]]) {
        const button = document.createElement("button"); button.type = "button"; button.className = "btn btn-default btn-sm mr-1"; button.textContent = t(key); button.disabled = inFlight; button.addEventListener("click", handler); actions.append(button);
      }
      tr.append(actions); $("records-body").append(tr);
    }
    $("empty-records").textContent = rows.length ? t("ui.no_filtered_records") : t("ui.no_records");
    $("empty-records").hidden = pageRows.length > 0;
  }

  function editRecord(row) {
    editing = row;
    renderSelectors(); controls.product.value = row.product;
    renderSelectors(); controls.market.value = row.market;
    renderSelectors(); controls.color.value = row.color;
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
    const state = readState();
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
    if (!$("entry-fields").disabled) controls.product.focus();
  });
  $("page-size-down").addEventListener("click", () => { pageSize = Math.max(5, pageSize - 5); currentPage = 1; render(); });
  $("page-size-up").addEventListener("click", () => { pageSize = Math.min(50, pageSize + 5); currentPage = 1; render(); });
  $("previous-page").addEventListener("click", () => { currentPage = Math.max(1, currentPage - 1); render(); });
  $("next-page").addEventListener("click", () => { currentPage += 1; render(); });
  $("fullscreen-button").addEventListener("click", toggleFullscreen);
  document.addEventListener("fullscreenchange", updateFullscreenButton);
  $("network-button").addEventListener("click", checkConnection);
  $("open-device-settings").addEventListener("click", () => {
    deviceSettings.showModal();
    $("open-device-settings").setAttribute("aria-expanded", "true");
    $("device-id").focus();
  });
  $("close-device-settings").addEventListener("click", closeDeviceSettings);
  deviceSettings.addEventListener("close", () => $("open-device-settings").setAttribute("aria-expanded", "false"));
  $("register-device").addEventListener("click", () => deviceAction(true));
  $("check-device").addEventListener("click", () => deviceAction(false));
  $("sync").addEventListener("click", syncQueue);
  $("cancel-edit").addEventListener("click", cancelEdit);
  window.addEventListener("online", () => { connected = true; render(); if (deviceId) deviceAction(false); });
  window.addEventListener("offline", () => { connected = false; render(); });
  window.addEventListener("storage", (event) => { if (event.key === stateKey()) render(); });
  setInterval(() => { if (navigator.onLine) syncQueue(); }, 15000);
  try { loadCache(); if (deviceId && navigator.onLine) deviceAction(false); }
  catch (error) {
    $("entry-fields").disabled = true;
    notice(error.message === t("ui.storage_error") ? error.message : t("error.unexpected"), true);
  }
})();
