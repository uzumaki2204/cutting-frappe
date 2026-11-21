"""Import product cutting standards from a private Excel workbook."""

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from io import BytesIO
from math import isfinite, ulp
from pathlib import Path
from zipfile import BadZipFile

import frappe
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException


MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
HEADERS = {
    "product_code": ("product code", "mã hàng"),
    "rate": ("cutting standard (m/pcs)", "cutting standard", "định mức", "định mức cắt"),
}


def _invalid(text):
    frappe.throw(frappe._(text), frappe.ValidationError)


def _private_workbook(file_id):
    doc = frappe.get_doc("File", file_id)
    doc.check_permission("read")
    path = Path(doc.get_full_path()).resolve()
    root = Path(frappe.get_site_path("private")).resolve()
    if not doc.is_private or not doc.file_name.lower().endswith(".xlsx") or not path.is_relative_to(root):
        _invalid("Upload a private .xlsx file.")
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        _invalid("The Excel file must be under 5 MB.")
    return path.read_bytes()


def _rate(value, row_number):
    try:
        rate = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        _invalid(f"Row {row_number}: cutting standard must be a positive number with at most 5 decimal places.")
    if isinstance(value, float) and isfinite(value):
        rounded = Decimal(str(round(value, 5)))
        if abs(rate - rounded) <= Decimal(str(ulp(value))) * 2:
            rate = rounded
    if not rate.is_finite() or rate <= 0 or rate.normalize().as_tuple().exponent < -5:
        _invalid(f"Row {row_number}: cutting standard must be a positive number with at most 5 decimal places.")
    return rate


def _parse(content):
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)
        header = next(rows, ())
        names = {str(value or "").strip().casefold(): index for index, value in enumerate(header)}
        columns = {}
        for key, aliases in HEADERS.items():
            match = next((names[name] for name in aliases if name in names), None)
            if match is None:
                _invalid("The Excel file needs Product Code and Cutting Standard (m/pcs) columns.")
            columns[key] = match
        result = []
        for row_number, row in enumerate(rows, 2):
            if not any(value is not None and str(value).strip() for value in row):
                continue
            if len(result) >= MAX_ROWS:
                _invalid("The Excel file may contain at most 5000 data rows.")
            raw_code = row[columns["product_code"]] if columns["product_code"] < len(row) else None
            if not isinstance(raw_code, str) or not raw_code.strip():
                _invalid(f"Row {row_number}: Product Code must be text.")
            code = raw_code.strip()
            raw_rate = row[columns["rate"]] if columns["rate"] < len(row) else None
            result.append((row_number, code, raw_rate))
        if not result:
            _invalid("The Excel file has no data rows.")
        return result
    except (OSError, ValueError, TypeError, BadZipFile, InvalidFileException) as exc:
        if isinstance(exc, frappe.ValidationError):
            raise
        _invalid("Could not read the .xlsx file.")
    finally:
        if "workbook" in locals():
            workbook.close()


def _products(codes):
    found = defaultdict(list)
    for offset in range(0, len(codes), 200):
        batch = codes[offset:offset + 200]
        for product in frappe.get_all("Product", filters={"product_code": ["in", batch]},
                                      fields=["name", "product_code"], limit=len(batch) * 2):
            found[product.product_code.strip().casefold()].append(product.name)
    return found


@frappe.whitelist(methods=["POST"])
def import_workbook(file_id: str):
    if not frappe.has_permission("Cutting Standard", "create") or not frappe.has_permission("Cutting Standard", "write"):
        frappe.throw(frappe._("Cutting Manager role is required."), frappe.PermissionError)
    entries = _parse(_private_workbook(file_id))
    products = _products([code for _, code, _ in entries])
    resolved = []
    skipped = 0
    seen = set()
    for row_number, code, raw_rate in entries:
        names = products.get(code.casefold(), [])
        if not names:
            skipped += 1
            continue
        if len(names) != 1:
            _invalid(f"Row {row_number}: Product Code {code} matches multiple Products.")
        if code.casefold() in seen:
            _invalid(f"Row {row_number}: duplicate Product Code {code}.")
        seen.add(code.casefold())
        resolved.append((names[0], code, _rate(raw_rate, row_number)))
    created = updated = 0
    for product, code, rate in resolved:
        name = frappe.db.get_value("Cutting Standard", {"product": product}, "name")
        doc = frappe.get_doc("Cutting Standard", name) if name else frappe.new_doc("Cutting Standard")
        doc.product_code = code
        doc.rate_m_per_piece = float(rate)
        if name:
            doc.save()
            updated += 1
        else:
            doc.insert()
            created += 1
    return {"created": created, "updated": updated, "skipped": skipped}
