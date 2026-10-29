"""Cutting record validation and append-only audit snapshots."""

import hashlib
from datetime import datetime, timezone

import frappe
from frappe.model.document import Document

from cutting.i18n import message


SNAPSHOT_FIELDS = (
    "product", "color", "market", "product_code_identifier", "quantity",
    "occurred_at", "company", "device", "device_uid", "local_event_id", "source",
)
EDITABLE_FIELDS = ("product", "color", "market", "product_code_identifier", "quantity", "company")
IDENTITY_FIELDS = ("device", "device_uid", "local_event_id", "event_uid", "occurred_at", "source")


def _fail(key):
    frappe.throw(message(key), frappe.ValidationError)


def event_uid(device, local_event_id):
    if not device or not local_event_id:
        return None
    return hashlib.sha256(f"{device}|{str(local_event_id).casefold()}".encode("utf-8")).hexdigest()


def _exists(doctype, name):
    return bool(name and frappe.db.exists(doctype, str(name)))


def _active(doctype, name):
    if not _exists(doctype, name):
        return False
    return not frappe.get_meta(doctype).has_field("is_active") or bool(frappe.db.get_value(doctype, name, "is_active"))


def _valid_variant(product, color, market):
    rows = frappe.get_all(
        "Product Variant",
        filters={"product": product, "color": color, "market": market, "is_active": 1},
        fields=["name", "size"],
        limit_page_length=100,
    )
    return any(row.size for row in rows)


def utc_db_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")


def write_history(doc, action):
    values = {name: doc.get(name) for name in SNAPSHOT_FIELDS}
    values.update({
        "doctype": "Cutting History",
        "cutting_record": doc.name,
        "action": action,
        "actor": frappe.session.user,
        "note": doc.note,
    })
    frappe.get_doc(values).insert(ignore_permissions=True)


class CuttingRecord(Document):
    def validate(self):
        self.product_code_identifier = str(self.product_code_identifier or "").strip()
        if not self.product_code_identifier or len(self.product_code_identifier) > 100:
            _fail("error.identifier")
        try:
            quantity = int(self.quantity)
        except (TypeError, ValueError):
            _fail("error.quantity")
        if not 1 <= quantity <= 2147483647 or str(self.quantity).strip() not in {str(quantity), f"{quantity}.0"}:
            _fail("error.quantity")
        self.quantity = quantity
        self.local_event_id = str(self.local_event_id or "").strip() or None
        if self.local_event_id and len(self.local_event_id) > 100:
            _fail("error.event_id")
        if self.source not in ("Cutting", "Import"):
            _fail("error.import_source")
        if not self.occurred_at:
            _fail("error.input")
        for doctype, value in (("Product", self.product), ("Color", self.color), ("Market", self.market)):
            if not _exists(doctype, value):
                _fail("error.master")
        if self.device:
            if not _exists("Factory Device", self.device):
                _fail("error.device_missing")
            device_company = frappe.db.get_value("Factory Device", self.device, "company")
            if self.company and device_company and self.company != device_company:
                _fail("error.device_company")
            self.company = device_company or self.company
            self.device_uid = self.device_uid or self.device
        self.event_uid = event_uid(self.device, self.local_event_id)
        previous = self.get_doc_before_save()
        if previous:
            if any((previous.get(field) or None) != (self.get(field) or None) for field in IDENTITY_FIELDS):
                _fail("error.immutable")
            state_changed = bool(previous.is_deleted) != bool(self.is_deleted)
            if state_changed and not self.flags.get("cutting_state_action"):
                _fail("error.state_action")
            if previous.is_deleted and not state_changed:
                _fail("error.restore_first")
        if (self.source == "Cutting" or self.flags.get("cutting_validate_active")) and not self.flags.get("cutting_state_action"):
            if not self.device:
                _fail("error.device_missing")
            if not all(_active(doctype, value) for doctype, value in (
                ("Product", self.product), ("Color", self.color), ("Market", self.market)
            )):
                _fail("error.master")
            if not _valid_variant(self.product, self.color, self.market):
                _fail("error.variant")

    def after_insert(self):
        write_history(self, "Import" if self.source == "Import" else "Create")

    def on_update(self):
        previous = self.get_doc_before_save()
        if not previous:
            return
        if bool(previous.is_deleted) != bool(self.is_deleted):
            action = "Delete" if self.is_deleted else "Restore"
        elif any(previous.get(field) != self.get(field) for field in EDITABLE_FIELDS):
            action = "Update"
        else:
            return
        write_history(self, action)

    def on_trash(self):
        _fail("error.use_soft_delete")

    def set_deleted(self, deleted):
        from cutting.access import require_manager

        require_manager()
        if bool(self.is_deleted) == bool(deleted):
            _fail("error.record_deleted" if deleted else "error.not_deleted")
        self.flags.cutting_state_action = "Delete" if deleted else "Restore"
        self.is_deleted = int(bool(deleted))
        self.deleted_at = utc_db_now() if deleted else None
        self.deleted_by = frappe.session.user if deleted else None
        self.save()
