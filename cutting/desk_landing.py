"""Open the business workspace for users who selected it as their default."""

import frappe


WORKSPACE = "TRIM and Cutting"
WORKSPACE_PATH = "/desk/trim-and-cutting"
LOGIN_PATHS = {"/api/method/login", "/api/v1/method/login"}


def open_default_workspace(response, request):
    if not _uses_business_workspace():
        return

    if request.method == "GET" and request.path == "/" and response.status_code == 200:
        response.status_code = 302
        response.headers["Location"] = WORKSPACE_PATH
        response.set_data("")
    elif request.method == "POST" and request.path in LOGIN_PATHS and response.is_json:
        _set_login_destination(response)


def _uses_business_workspace():
    user = frappe.session.user
    return user != "Guest" and frappe.get_cached_value("User", user, "default_workspace") == WORKSPACE


def _set_login_destination(response):
    if response.status_code != 200:
        return
    payload = response.get_json(silent=True)
    if not isinstance(payload, dict) or "home_page" not in payload:
        return
    payload["home_page"] = WORKSPACE_PATH
    response.set_data(frappe.as_json(payload))
