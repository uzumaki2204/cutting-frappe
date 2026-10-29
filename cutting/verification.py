"""CLI-only test fixtures and a transactional installation smoke check."""

import uuid

import frappe

from cutting import api, reporting
from cutting.cutting.doctype.cutting_record.cutting_record import event_uid
from cutting.i18n import message


def _fixtures():
    suffix = uuid.uuid4().hex[:10]
    code = "CUTTEST-" + suffix
    company = frappe.get_doc({"doctype": "Company", "company_code": code, "company_name": code, "active": 1}).insert(ignore_permissions=True)
    product = frappe.get_doc({"doctype": "Product", "product_code": code, "product_name": code, "is_active": 1}).insert(ignore_permissions=True)
    color = frappe.get_doc({"doctype": "Color", "color_code": code, "color_name": code, "color": "#" + suffix[:6], "is_active": 1}).insert(ignore_permissions=True, set_name=code)
    market = frappe.get_doc({"doctype": "Market", "code": code, "name_en": code, "is_active": 1}).insert(ignore_permissions=True)
    size_type = frappe.get_meta("Product Variant").get_field("size").options
    size = frappe.get_doc({"doctype": size_type, "size_label": code, "size_code": code, "is_active": 1}).insert(ignore_permissions=True, set_name=code)
    frappe.get_doc({"doctype": "Product Variant", "product": product.name, "color": color.name, "market": market.name, "size": size.name, "is_active": 1}).insert(ignore_permissions=True)
    device_id = str(uuid.uuid4())
    device_values = {"doctype": "Factory Device", "name": device_id, "device_name": code, "company": company.name, "status": "Approved", "is_active": 1}
    for field in ("device_id", "device_uid"):
        if frappe.get_meta("Factory Device").has_field(field):
            device_values[field] = device_id
    device = frappe.get_doc(device_values).insert(ignore_permissions=True, set_name=device_id)
    return {"company": company.name, "product": product.name, "color": color.name, "market": market.name, "device": device.name}


def seed(password: str):
    """Create persistent fixtures only on an explicitly enabled Cutting test site."""
    if not str(frappe.local.site).startswith("cutting-test.") or not frappe.conf.get("allow_tests"):
        frappe.throw(message("error.test_site_only"), frappe.PermissionError)
    values = _fixtures()
    email = "cutting-test-" + uuid.uuid4().hex[:8] + "@example.invalid"
    user_values = {"doctype": "User", "email": email, "first_name": "Cutting Test", "enabled": 1,
                   "user_type": "System User", "send_welcome_email": 0,
                   "roles": [{"role": "Cutting Manager"}]}
    if frappe.get_meta("User").has_field("company"):
        user_values["company"] = values["company"]
    user = frappe.get_doc(user_values).insert(ignore_permissions=True)
    from frappe.utils.password import update_password

    update_password(user.name, password)
    return {**values, "user": user.name}


def smoke():
    """Exercise one tablet record and one import record, then roll everything back."""
    original_user = frappe.session.user
    savepoint = "cutting_smoke_" + uuid.uuid4().hex[:10]
    frappe.db.savepoint(savepoint)
    try:
        frappe.set_user("Administrator")
        fixtures = _fixtures()
        now = api._clock()
        item = {"local_event_id": uuid.uuid4().hex, "product": fixtures["product"],
                "color": fixtures["color"], "market": fixtures["market"],
                "product_code_identifier": "CUTTEST", "quantity": 1, "occurred_at": now["server_now_utc"]}
        api.bootstrap(fixtures["device"])
        api.sync_records(fixtures["device"], [item])
        api.sync_records(fixtures["device"], [item])
        name = frappe.db.get_value("Cutting Record", {"event_uid": event_uid(fixtures["device"], item["local_event_id"])}, "name")
        assert name
        api.soft_delete(name)
        api.restore(name)
        imported = frappe.get_doc({"doctype": "Cutting Record", "product": fixtures["product"],
                                   "color": fixtures["color"], "market": fixtures["market"],
                                   "product_code_identifier": "CUTTEST-IMPORT", "quantity": 1,
                                   "occurred_at": api._site_db(now["server_now_utc"]), "source": "Import"}).insert()
        assert not imported.device
        result = reporting.report_summary(now["server_date_key"], now["server_date_key"], {"device": fixtures["device"]})
        assert result["metadata"]["sourceRowCount"] == 1
        assert len(api.history(name)) == 3
        return {"bootstrap": True, "idempotent_sync": True, "delete_restore": True,
                "import_without_device": True, "history": True, "reports": True, "rolled_back": True}
    finally:
        frappe.db.rollback(save_point=savepoint)
        frappe.set_user(original_user)
