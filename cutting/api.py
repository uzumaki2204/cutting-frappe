"""Tablet Cutting API and manager actions."""

import hashlib
import json
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import frappe

from cutting.access import require_manager, require_viewer
from cutting.cutting.doctype.cutting_record.cutting_record import event_uid, utc_db_now
from cutting.i18n import catalog, message
from cutting import devices


BATCH_LIMIT = 500


@frappe.whitelist(allow_guest=True, methods=["GET"])
def translations(lang: str = "vi"):
    return catalog().get(str(lang).split("-")[0], catalog()["vi"])


@frappe.whitelist(allow_guest=True, methods=["GET"])
def device_epoch():
    import importlib.util

    if importlib.util.find_spec("factory_management.data_epoch") is None:
        return {"generation": ""}
    from factory_management import data_epoch

    return data_epoch.current()


@frappe.whitelist(allow_guest=True, methods=["POST"])
def register_device(id: str | None = None, device_name: str | None = None):
    return devices.register(id, device_name)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def check_device(id: str | None = None):
    return devices.check(id)


def _fail(key, error=frappe.ValidationError, **values):
    frappe.throw(message(key, **values), error)


def _data(value, fallback=None):
    if value is None:
        return fallback
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            _fail("error.input")
    return value


def _device(id):
    device = devices.find(id)
    if device.status != "Approved" or not device.is_active:
        _fail("error.device_pending", frappe.PermissionError)
    if not device.company:
        _fail("error.device_company", frappe.PermissionError)
    return device


def _zone():
    name = frappe.db.get_single_value("System Settings", "time_zone") or "Asia/Ho_Chi_Minh"
    try:
        return ZoneInfo(name)
    except KeyError:
        return ZoneInfo("Asia/Ho_Chi_Minh")


def _clock():
    now = datetime.now(timezone.utc)
    local = now.astimezone(_zone())
    return {
        "server_now_utc": now.isoformat(),
        "server_utc_offset_minutes": int(local.utcoffset().total_seconds() // 60),
        "server_date_key": local.date().isoformat(),
    }


def _utc_db(value):
    if not value:
        return utc_db_now()
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        _fail("error.input")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")


def _event_id(item):
    if not isinstance(item, dict):
        _fail("error.input")
    value = str(item.get("local_event_id") or "").strip()
    if not value or len(value) > 100:
        _fail("error.event_id")
    return value


def _selection(item):
    code = str(item.get("product_code_identifier") or "").strip()
    if not code or len(code) > 100:
        _fail("error.identifier")
    try:
        quantity = int(item.get("quantity"))
    except (TypeError, ValueError):
        _fail("error.quantity")
    if not 1 <= quantity <= 2147483647 or str(item.get("quantity")).strip() not in {str(quantity), f"{quantity}.0"}:
        _fail("error.quantity")
    return {
        "product": item.get("product"),
        "color": item.get("color"),
        "market": item.get("market"),
        "product_code_identifier": code,
        "quantity": quantity,
    }


def _record_for_device(device, local_event_id):
    name = frappe.db.get_value("Cutting Record", {"event_uid": event_uid(device.name, local_event_id)}, "name")
    if not name and frappe.db.exists("Cutting Record", local_event_id):
        name = local_event_id
    if not name:
        _fail("error.record_missing", frappe.DoesNotExistError)
    record = frappe.get_doc("Cutting Record", name)
    if record.device != device.name:
        _fail("error.record_owner", frappe.PermissionError)
    return record


def _option(row, code, title, **extra):
    value = {"id": row.name, "code": row.get(code) or "", "name": row.get(title) or ""}
    value.update(extra)
    return value


@frappe.whitelist(allow_guest=True, methods=["GET"])
def bootstrap(id: str | None = None):
    _device(id)
    product_fields = ["name", "product_code", "product_name"]
    season_field = "production_season" if frappe.get_meta("Product").has_field("production_season") else "season"
    if frappe.get_meta("Product").has_field(season_field):
        product_fields.append(season_field)
    products = frappe.get_all("Product", fields=product_fields, filters={"is_active": 1}, limit_page_length=20000)
    color_meta = frappe.get_meta("Color")
    color_code = "color_code" if color_meta.has_field("color_code") else "name"
    color_title = "color_name" if color_meta.has_field("color_name") else "name"
    colors = frappe.get_all("Color", fields=list(dict.fromkeys(["name", color_code, color_title])), filters={"is_active": 1} if color_meta.has_field("is_active") else {}, limit_page_length=20000)
    markets = frappe.get_all("Market", fields=["name", "code", "name_en"], filters={"is_active": 1}, limit_page_length=20000)
    seasons = frappe.get_all("Production Season", fields=["name", "season_code", "season_name"], filters={"is_active": 1}, limit_page_length=20000)
    variants = frappe.get_all("Product Variant", fields=["name", "product", "color", "market", "size"], filters={"is_active": 1}, limit_page_length=20000)
    product_ids = {row.name for row in products}
    color_ids = {row.name for row in colors}
    market_ids = {row.name for row in markets}
    season_names = {row.season_code: row.name for row in seasons}
    catalog = {
        "products": [_option(row, "product_code", "product_name", season_id=season_names.get(row.get(season_field), row.get(season_field))) for row in products],
        "colors": [_option(row, color_code, color_title) for row in colors],
        "markets": [_option(row, "code", "name_en") for row in markets],
        "seasons": [_option(row, "season_code", "season_name") for row in seasons],
        "product_variants": [
            {"product": row.product, "color": row.color, "market": row.market}
            for row in variants
            if row.size and row.product in product_ids and row.color in color_ids and row.market in market_ids
        ],
    }
    version = hashlib.sha256(json.dumps(catalog, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return {"catalog": catalog, "catalog_version": version, **_clock()}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def sync_records(id: str | None = None, records: list | str | None = None, updates: list | str | None = None, deletes: list | str | None = None):
    savepoint = "cutting_sync_" + frappe.generate_hash(length=10)
    frappe.db.savepoint(savepoint)
    try:
        return _sync_records(id, records, updates, deletes)
    except Exception:
        try:
            frappe.db.rollback(save_point=savepoint)
        except Exception:
            frappe.db.rollback()
        raise


def _sync_records(id, records, updates, deletes):
    device = _device(id)
    creates = _data(records, [])
    edits = _data(updates, [])
    removals = _data(deletes, [])
    if not all(isinstance(value, list) for value in (creates, edits, removals)):
        _fail("error.input")
    if sum(len(value) for value in (creates, edits, removals)) > BATCH_LIMIT:
        _fail("error.batch_limit", limit=BATCH_LIMIT)
    accepted = {"records": [], "updates": [], "deletes": []}
    for item in creates:
        local_id = _event_id(item)
        values = _selection(item)
        uid = event_uid(device.name, local_id)
        existing_name = frappe.db.get_value("Cutting Record", {"event_uid": uid}, "name")
        if not existing_name:
            frappe.get_doc({
                "doctype": "Cutting Record", **values,
                "company": device.company,
                "device": device.name,
                "device_uid": device.name,
                "local_event_id": local_id,
                "occurred_at": _utc_db(item.get("occurred_at")),
                "source": "Cutting",
            }).insert(ignore_permissions=True)
        accepted["records"].append(local_id)
    for item in edits:
        local_id = _event_id(item)
        record = _record_for_device(device, local_id)
        if record.is_deleted:
            _fail("error.restore_first")
        record.update(_selection(item))
        record.flags.cutting_validate_active = True
        record.save(ignore_permissions=True)
        accepted["updates"].append(local_id)
    for item in removals:
        local_id = _event_id(item)
        record = _record_for_device(device, local_id)
        if not record.is_deleted:
            record.flags.cutting_state_action = "Delete"
            record.is_deleted = 1
            record.deleted_at = utc_db_now()
            record.deleted_by = device.name
            record.save(ignore_permissions=True)
        accepted["deletes"].append(local_id)
    return {
        "accepted_count": len(accepted["records"]),
        "accepted_local_event_ids": accepted["records"],
        "accepted_update_count": len(accepted["updates"]),
        "accepted_update_local_event_ids": accepted["updates"],
        "accepted_delete_count": len(accepted["deletes"]),
        "accepted_delete_local_event_ids": accepted["deletes"],
        "notice": message("ok.synced"),
    }


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_device_records(id: str | None = None):
    device = _device(id)
    now = datetime.now(_zone())
    start = datetime.combine(now.date(), time.min, tzinfo=_zone()).astimezone(timezone.utc)
    end = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=_zone()).astimezone(timezone.utc)
    fields = ["name", "product", "color", "market", "product_code_identifier", "quantity", "local_event_id", "occurred_at", "creation"]
    rows = frappe.get_all(
        "Cutting Record", fields=fields,
        filters=[["device", "=", device.name], ["is_deleted", "=", 0], ["occurred_at", ">=", start.strftime("%Y-%m-%d %H:%M:%S")], ["occurred_at", "<", end.strftime("%Y-%m-%d %H:%M:%S")]],
        order_by="occurred_at desc", limit_page_length=200,
    )
    for row in rows:
        row.local_event_id = row.local_event_id or row.name
    return rows


@frappe.whitelist(methods=["POST"])
def soft_delete(name: str):
    require_manager()
    record = frappe.get_doc("Cutting Record", name)
    record.set_deleted(True)
    return {"name": record.name, "notice": message("ok.deleted")}


@frappe.whitelist(methods=["POST"])
def restore(name: str):
    require_manager()
    record = frappe.get_doc("Cutting Record", name)
    record.set_deleted(False)
    return {"name": record.name, "notice": message("ok.restored")}


@frappe.whitelist(methods=["GET"])
def history(name: str):
    require_viewer()
    if not frappe.db.exists("Cutting Record", name):
        _fail("error.record_missing", frappe.DoesNotExistError)
    return frappe.get_all(
        "Cutting History", filters={"cutting_record": name},
        fields=["name", "action", "product", "color", "market", "product_code_identifier", "quantity", "device", "occurred_at", "actor", "note", "creation"],
        order_by="creation desc", limit_page_length=1000,
    )
