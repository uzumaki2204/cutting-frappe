(function (scope, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else scope.CuttingDevice = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

  function parseId(value) {
    let candidate = String(value || "").trim();
    if (!candidate) return "";
    try {
      if (candidate.startsWith("{")) {
        const payload = JSON.parse(candidate);
        candidate = String(payload.id || payload.deviceId || "").trim();
      } else if (/^https?:\/\//i.test(candidate)) {
        const url = new URL(candidate);
        candidate = String(url.searchParams.get("id") || url.searchParams.get("deviceId") || "").trim();
      }
    } catch (_) { return ""; }
    return uuid.test(candidate) ? candidate.toLowerCase() : "";
  }

  function clearStorage(storage) {
    const keys = [];
    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index);
      if (key && key.startsWith("cutting.")) keys.push(key);
    }
    keys.forEach((key) => storage.removeItem(key));
    return keys;
  }

  return { parseId, clearStorage };
});
