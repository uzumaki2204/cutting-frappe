"""History snapshots are immutable to edits; Frappe Delete permission controls removal."""

import frappe
from frappe.model.document import Document

from cutting.i18n import message


class CuttingHistory(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw(message("error.history_immutable"), frappe.PermissionError)
