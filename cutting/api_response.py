"""Remove Frappe's method wrapper from the .NET-compatible Summary response."""

import frappe


SUMMARY_METHOD = "cutting.reporting.summary"


def direct_summary_response(response, request):
    path = request.path.rstrip("/")
    if path not in (f"/api/method/{SUMMARY_METHOD}", f"/api/v1/method/{SUMMARY_METHOD}"):
        return
    if not response.is_json:
        return
    payload = response.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("message"), dict):
        return
    result = payload["message"]
    if not all(key in result for key in ("success", "code", "message", "data", "errors")):
        return
    response.set_data(frappe.as_json(result))
