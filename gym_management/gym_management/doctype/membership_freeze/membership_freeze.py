import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, getdate


class MembershipFreeze(Document):
    def validate(self):
        if not self.freeze_from or not self.freeze_to:
            return

        freeze_from = getdate(self.freeze_from)
        freeze_to = getdate(self.freeze_to)

        if freeze_to <= freeze_from:
            frappe.throw(_("Freeze To must be after Freeze From."))

        self.days = date_diff(freeze_to, freeze_from) + 1
