"""Apply the Cutting Record form change and index historical device identities."""

import frappe


def ensure_history_identity_index():
    frappe.db.add_index(
        "Cutting History",
        ["device", "local_event_id", "cutting_record"],
        "cutting_history_device_event",
    )


def execute():
    frappe.reload_doc("cutting", "doctype", "cutting_record")
    ensure_history_identity_index()
