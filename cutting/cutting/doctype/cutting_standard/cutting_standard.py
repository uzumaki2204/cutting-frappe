"""Validate a product's current cutting standard."""

from decimal import Decimal, InvalidOperation

import frappe
from frappe.model.document import Document

from cutting.i18n import message


class CuttingStandard(Document):
    def validate(self):
        try:
            rate = Decimal(str(self.rate_m_per_piece))
        except InvalidOperation:
            rate = Decimal(0)
        if not rate.is_finite() or rate <= 0 or rate.normalize().as_tuple().exponent < -5:
            frappe.throw(message("error.cutting_standard_invalid"))
