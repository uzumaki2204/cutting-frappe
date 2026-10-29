"""Cutting uses approved devices already maintained by Factory Management."""

import importlib.util

import frappe
from frappe.utils import now_datetime

from cutting.i18n import message


def find(id):
    name = str(id or "").strip()
    if not name:
        frappe.throw(message("error.device_missing"), frappe.DoesNotExistError)
    if not frappe.db.exists("Factory Device", name) and frappe.get_meta("Factory Device").has_field("device_id"):
        name = frappe.db.get_value("Factory Device", {"device_id": name}, "name")
    if not name or not frappe.db.exists("Factory Device", name):
        frappe.throw(message("error.device_missing"), frappe.DoesNotExistError)
    return frappe.get_doc("Factory Device", name)


def info(device):
    return {"id": device.name, "device_id": device.name, "device_name": device.device_name,
            "status": device.status, "is_active": bool(device.is_active),
            "company": device.company, "factory": device.factory, "line": device.line}


def _require_current_epoch():
    if importlib.util.find_spec("factory_management.data_epoch") is not None:
        from factory_management import data_epoch

        data_epoch.require_current()


def _approved(id):
    device = find(id)
    if device.status != "Approved" or not device.is_active:
        frappe.throw(message("error.device_pending"), frappe.PermissionError)
    if not device.company:
        frappe.throw(message("error.device_company"), frappe.PermissionError)
    return device


def register(id=None, device_name=None):
    """Activate an existing Factory Device; never create or rename one."""
    _require_current_epoch()
    device = _approved(id)
    if frappe.get_meta("Factory Device").has_field("last_seen_at"):
        frappe.db.set_value("Factory Device", device.name, "last_seen_at", now_datetime(), update_modified=False)
    return {"device": info(device), "notice": message("ok.device_activated")}


def check(id):
    _require_current_epoch()
    return info(_approved(id))
