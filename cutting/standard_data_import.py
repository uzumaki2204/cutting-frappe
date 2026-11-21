"""Connect Cutting Standard to Frappe's Data Import workflow."""

import frappe
from frappe.core.doctype.data_import.import_provider import ImportProvider
from frappe.core.doctype.data_import.importer import (
    ACTION_INSERT,
    ACTION_UPDATE,
    INSERT,
    UPDATE,
)


class CuttingStandardImportProvider(ImportProvider):
    def get_import_fields(self):
        meta = frappe.get_meta("Cutting Standard")
        return {
            "fields": [meta.get_field(field).as_dict() for field in ("product_code", "rate_m_per_piece")],
            "child_tables": [],
        }

    def import_row(self, importer, doc):
        code = str(doc.get("product_code") or "").strip()
        if not code:
            frappe.throw(frappe._("Product Code is required."))

        name = frappe.db.get_value("Cutting Standard", {"product_code": code}, "name")
        if name and importer.import_type == INSERT:
            frappe.throw(frappe._("Cutting Standard for Product Code {0} already exists.").format(code))
        if not name and importer.import_type == UPDATE:
            frappe.throw(frappe._("Cutting Standard for Product Code {0} does not exist.").format(code))

        doc["product_code"] = code
        if name:
            doc["name"] = name
            return importer.update_record(doc, raise_if_no_changes=False), ACTION_UPDATE
        doc.pop("name", None)
        return importer.insert_record(doc), ACTION_INSERT


def skip_missing_products(doc, method=None):
    if doc.reference_doctype != "Cutting Standard" or not doc.import_file:
        return

    payloads = doc.get_importer().import_file.get_payloads_for_import()
    codes = sorted({str(payload.doc.get("product_code") or "").strip() for payload in payloads} - {""})
    existing = set()
    for batch_start in range(0, len(codes), 200):
        batch = codes[batch_start:batch_start + 200]
        existing.update(frappe.get_all("Product", filters={"product_code": ["in", batch]},
                                       pluck="product_code", limit=len(batch) * 2))

    known = {code.casefold() for code in existing}
    skipped = {row.row_number for row in doc.skipped_rows}
    for payload in payloads:
        code = str(payload.doc.get("product_code") or "").strip()
        if not code or code.casefold() in known:
            continue
        for row in payload.rows:
            if row.row_number not in skipped:
                doc.append("skipped_rows", {
                    "row_number": row.row_number,
                    "row_data": frappe.as_json(row.data),
                })
                skipped.add(row.row_number)
