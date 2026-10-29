import frappe

from cutting.i18n import message


def can_open():
    return True


def has_role(*roles):
    user = frappe.session.user
    return user == "Administrator" or bool(set(frappe.get_roles(user)) & {"System Manager", *roles})


def require_viewer():
    if not has_role("Cutting Viewer", "Cutting Manager"):
        frappe.throw(message("error.permission"), frappe.PermissionError)


def require_manager():
    if not has_role("Cutting Manager"):
        frappe.throw(message("error.permission"), frappe.PermissionError)
