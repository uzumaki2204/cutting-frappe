"""Reuse modern shared device APIs; adapt older QC-specific registration safely."""

import inspect
import uuid

import frappe

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


def _modern_shared_api():
    from factory_management import api

    return api if "id" in inspect.signature(api.register_device).parameters else None


def register(id=None, device_name=None):
    shared = _modern_shared_api()
    if shared:
        return shared.register_device(id=id, device_name=device_name)
    try:
        name = str(uuid.UUID(str(id))) if id else str(uuid.uuid4())
    except (TypeError, ValueError):
        frappe.throw(message("error.input"), frappe.ValidationError)
    if frappe.db.exists("Factory Device", name):
        device = find(name)
    else:
        values = {"doctype": "Factory Device", "name": name, "device_name": str(device_name or "")[:140], "status": "Pending", "is_active": 1}
        meta = frappe.get_meta("Factory Device")
        for field in ("device_id", "device_uid"):
            if meta.has_field(field):
                values[field] = name
        device = frappe.get_doc(values).insert(ignore_permissions=True, set_name=name)
    return {"device": info(device), "notice": message("ok.device_approved" if device.status == "Approved" and device.is_active else "ok.device_pending")}


def check(id):
    shared = _modern_shared_api()
    if shared:
        return shared.check_device(id=id)
    return info(find(id))
