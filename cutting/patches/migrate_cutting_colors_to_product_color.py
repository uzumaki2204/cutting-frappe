"""Move existing Cutting color links from Color to Product Color."""

import frappe

from cutting.i18n import message


CUTTING_DOCTYPES = ("Cutting Record", "Cutting History")


def _referenced_colors():
    names = set()
    for doctype in CUTTING_DOCTYPES:
        if not frappe.db.table_exists(doctype, cached=False):
            continue
        rows = frappe.db.sql(
            f"SELECT DISTINCT color FROM `tab{doctype}` "
            "WHERE color IS NOT NULL AND color != ''",
            as_list=True,
        )
        names.update(row[0] for row in rows if row[0])
    return names


def _resolve_color(name, legacy_color_meta):
    if frappe.db.exists("Product Color", name):
        return name
    if not legacy_color_meta or not legacy_color_meta.has_field("color_code"):
        return None
    color_code = frappe.db.get_value("Color", name, "color_code")
    if not color_code:
        return None
    matches = frappe.get_all(
        "Product Color",
        filters={"color_code": color_code},
        fields=["name"],
        limit_page_length=2,
    )
    return matches[0].name if len(matches) == 1 else None


def execute():
    """Preflight all references before updating either records or history."""
    referenced = _referenced_colors()
    if not referenced:
        return

    legacy_color_meta = frappe.get_meta("Color") if frappe.db.exists("DocType", "Color") else None
    mapping = {
        name: _resolve_color(name, legacy_color_meta)
        for name in referenced
    }
    unresolved = sorted(name for name, target in mapping.items() if not target)
    if unresolved:
        frappe.throw(
            message(
                "error.color_migration",
                count=len(unresolved),
                values=", ".join(unresolved[:10]),
            ),
            frappe.ValidationError,
        )

    for doctype in CUTTING_DOCTYPES:
        if not frappe.db.table_exists(doctype, cached=False):
            continue
        for source, target in mapping.items():
            if source != target:
                frappe.db.set_value(
                    doctype,
                    {"color": source},
                    "color",
                    target,
                    update_modified=False,
                )
