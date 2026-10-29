"""Install app-owned navigation without changing shared master DocTypes."""

import frappe

from cutting.i18n import message


REQUIRED_DOCTYPES = (
    "Company", "Product", "Product Variant", "Color", "Market",
    "Production Season", "Factory Device",
)
ROLES = ("Cutting Manager", "Cutting Viewer")


def before_install():
    for doctype in ("Web Page", "Builder Page"):
        if frappe.db.exists("DocType", doctype) and frappe.db.exists(doctype, {"route": "cutting", "published": 1}):
            frappe.throw(message("error.route_conflict", doctype=doctype))
    for doctype in REQUIRED_DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            frappe.throw(message("error.missing_doctype", doctype=doctype))
    for role in ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)


def after_install():
    after_migrate()


def after_migrate():
    import frappe.permissions

    for doctype in REQUIRED_DOCTYPES:
        frappe.permissions.setup_custom_perms(doctype)
        for role in ROLES:
            if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
                frappe.get_doc({
                    "doctype": "Custom DocPerm", "parent": doctype,
                    "parenttype": "DocType", "parentfield": "permissions",
                    "role": role, "permlevel": 0, "select": 1,
                }).insert(ignore_permissions=True)
    frappe.permissions.setup_custom_perms("Data Import")
    if not frappe.db.exists("Custom DocPerm", {"parent": "Data Import", "role": "Cutting Manager", "permlevel": 0}):
        frappe.get_doc({
            "doctype": "Custom DocPerm", "parent": "Data Import",
            "parenttype": "DocType", "parentfield": "permissions",
            "role": "Cutting Manager", "permlevel": 0, "if_owner": 1,
            "read": 1, "create": 1, "write": 1,
        }).insert(ignore_permissions=True)
    frappe.clear_cache()
