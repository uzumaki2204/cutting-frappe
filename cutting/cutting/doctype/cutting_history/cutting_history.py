"""History is an append-only record of Cutting operations."""

import frappe
from frappe.model.document import Document

from cutting.i18n import message


class CuttingHistory(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw(message("error.history_immutable"), frappe.PermissionError)

    def on_trash(self):
        frappe.throw(message("error.history_immutable"), frappe.PermissionError)
