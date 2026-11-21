"""Validate a product's current cutting standard."""

from decimal import Decimal, InvalidOperation
from math import isfinite, ulp

import frappe
from frappe.model.document import Document

from cutting.i18n import message


class CuttingStandard(Document):
    def validate(self):
        code = str(self.product_code or "").strip()
        if not code:
            frappe.throw(frappe._("Product Code is required."))
        products = frappe.get_all("Product", filters={"product_code": code},
                                  fields=["name", "product_code"], limit=2)
        if len(products) != 1:
            frappe.throw(frappe._("Product Code {0} must match exactly one Product.").format(code))
        self.product = products[0].name
        self.product_code = products[0].product_code
        try:
            rate = Decimal(str(self.rate_m_per_piece))
        except InvalidOperation:
            rate = Decimal(0)
        if isinstance(self.rate_m_per_piece, float) and isfinite(self.rate_m_per_piece):
            rounded = Decimal(str(round(self.rate_m_per_piece, 5)))
            if abs(rate - rounded) <= Decimal(str(ulp(self.rate_m_per_piece))) * 2:
                rate = rounded
        if not rate.is_finite() or rate <= 0 or rate.normalize().as_tuple().exponent < -5:
            frappe.throw(message("error.cutting_standard_invalid"))
        self.rate_m_per_piece = float(rate)
