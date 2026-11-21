"""Preserve linked cutting standards before Product Code becomes editable."""

import frappe


def execute():
    if not frappe.db.table_exists("Cutting Standard", cached=False):
        return

    frappe.db.sql("""
        UPDATE `tabCutting Standard` s
        INNER JOIN `tabProduct` p ON p.name = s.product
        SET s.product_code = p.product_code
        WHERE COALESCE(s.product_code, '') = ''
    """)
    missing = frappe.db.sql("""
        SELECT name FROM `tabCutting Standard`
        WHERE COALESCE(product_code, '') = '' LIMIT 5
    """, as_list=True)
    if missing:
        names = ", ".join(row[0] for row in missing)
        frappe.throw(frappe._("Cutting Standard has records without Product Code: {0}").format(names))

    duplicates = frappe.db.sql("""
        SELECT product_code FROM `tabCutting Standard`
        GROUP BY product_code HAVING COUNT(*) > 1 LIMIT 5
    """, as_list=True)
    if duplicates:
        codes = ", ".join(row[0] for row in duplicates)
        frappe.throw(frappe._("Cutting Standard has duplicate Product Codes: {0}").format(codes))
