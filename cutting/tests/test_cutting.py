import uuid

import frappe
from frappe.tests import IntegrationTestCase

from cutting import api, reporting
from cutting.cutting.doctype.cutting_record.cutting_record import event_uid


class TestCutting(IntegrationTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        suffix = uuid.uuid4().hex[:10]
        self.company = frappe.get_doc({"doctype": "Company", "company_code": "CUT-" + suffix, "company_name": suffix, "active": 1}).insert()
        self.product = frappe.get_doc({"doctype": "Product", "product_code": "CUT-" + suffix, "product_name": suffix, "is_active": 1}).insert()
        self.color = frappe.get_doc({"doctype": "Color", "color_code": "CUT-" + suffix, "color_name": suffix, "color": "#" + suffix[:6], "is_active": 1}).insert(set_name="CUT-" + suffix)
        self.market = frappe.get_doc({"doctype": "Market", "code": "CUT-" + suffix, "name_en": suffix, "is_active": 1}).insert()
        size_type = frappe.get_meta("Product Variant").get_field("size").options
        self.size = frappe.get_doc({"doctype": size_type, "size_label": "CUT-" + suffix, "size_code": "CUT-" + suffix, "is_active": 1}).insert(set_name="CUT-" + suffix)
        frappe.get_doc({"doctype": "Product Variant", "product": self.product.name, "color": self.color.name, "market": self.market.name, "size": self.size.name, "is_active": 1}).insert()
        device_id = str(uuid.uuid4())
        values = {"doctype": "Factory Device", "name": device_id, "device_name": "CUT-" + suffix, "company": self.company.name, "status": "Approved", "is_active": 1}
        for field in ("device_id", "device_uid"):
            if frappe.get_meta("Factory Device").has_field(field):
                values[field] = device_id
        self.device = frappe.get_doc(values).insert(set_name=device_id)

    def item(self, local_id="event-1", quantity=10):
        return {"local_event_id": local_id, "product": self.product.name, "color": self.color.name, "market": self.market.name, "product_code_identifier": "PLAN", "quantity": quantity, "occurred_at": "2026-10-29T01:00:00Z"}

    def record(self, local_id="event-1"):
        return frappe.get_doc("Cutting Record", {"event_uid": event_uid(self.device.name, local_id)})

    def test_replay_does_not_duplicate_or_overwrite_admin_edit(self):
        api.sync_records(self.device.name, [self.item()])
        record = self.record(); record.quantity = 12; record.save()
        response = api.sync_records(self.device.name, [self.item()])
        self.assertEqual(response["accepted_count"], 1)
        self.assertEqual(self.record().quantity, 12)
        self.assertEqual(frappe.db.count("Cutting Record", {"event_uid": event_uid(self.device.name, "event-1")}), 1)

    def test_invalid_batch_rolls_back_all_records_and_history(self):
        with self.assertRaises(frappe.ValidationError):
            api.sync_records(self.device.name, [self.item("good"), self.item("bad", 0)])
        self.assertFalse(frappe.db.exists("Cutting Record", {"event_uid": event_uid(self.device.name, "good")}))

    def test_pending_device_cannot_write(self):
        self.device.status = "Pending"; self.device.save()
        with self.assertRaises(frappe.PermissionError):
            api.sync_records(self.device.name, [self.item()])

    def test_tablet_rejects_inactive_product_and_variant(self):
        self.product.is_active = 0; self.product.save()
        with self.assertRaises(frappe.ValidationError):
            api.sync_records(self.device.name, [self.item()])
        self.product.is_active = 1; self.product.save()
        variant = frappe.get_doc("Product Variant", {"product": self.product.name})
        variant.is_active = 0; variant.save()
        with self.assertRaises(frappe.ValidationError):
            api.sync_records(self.device.name, [self.item()])
        self.assertFalse(frappe.db.exists("Cutting Record", {"device": self.device.name}))

    def test_update_delete_restore_and_append_only_history(self):
        api.sync_records(self.device.name, [self.item()])
        api.sync_records(self.device.name, updates=[self.item(quantity=20)])
        record = self.record(); api.soft_delete(record.name); api.restore(record.name)
        actions = [row.action for row in frappe.get_all("Cutting History", filters={"cutting_record": record.name}, fields=["action"], order_by="creation")]
        self.assertEqual(actions, ["Create", "Update", "Delete", "Restore"])
        history = frappe.get_doc("Cutting History", {"cutting_record": record.name})
        history.note = "changed"
        with self.assertRaises(frappe.PermissionError):
            history.save()

    def test_import_record_can_omit_device_but_not_master_links(self):
        values = self.item(); values.pop("local_event_id"); values["source"] = "Import"
        record = frappe.get_doc({"doctype": "Cutting Record", **values}).insert()
        self.assertFalse(record.device)
        second = frappe.get_doc({"doctype": "Cutting Record", **values}).insert()
        self.assertNotEqual(second.name, record.name)
        self.assertEqual(frappe.db.get_value("Cutting History", {"cutting_record": record.name}, "action"), "Import")
        values["product"] = "missing-product"
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc({"doctype": "Cutting Record", **values}).insert()

    def test_report_guards_and_weekly_grouping(self):
        api.sync_records(self.device.name, [self.item("one"), self.item("two", 5)])
        data = reporting.report_summary("2026-10-29", "2026-10-29", {"device": self.device.name})
        self.assertEqual(data["rows"][0]["quantity"], 15)
        self.assertEqual(data["rows"][0]["startOfWeek"], "2026-10-26")
        self.assertEqual(data["metadata"]["sourceRowCount"], 2)
        with self.assertRaises(frappe.ValidationError):
            reporting.report_detail("2026-10-01", "2026-10-09")
        with self.assertRaises(frappe.ValidationError):
            reporting.report_summary("2026-10-01", "2026-11-01")
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            reporting.admin_summary()
        frappe.set_user("Administrator")
