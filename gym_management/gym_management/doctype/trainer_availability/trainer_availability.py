import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_time

from gym_management.utils import format_time


class TrainerAvailability(Document):
    def validate(self):
        self.validate_time_range()
        self.validate_no_overlap()

    def validate_time_range(self):
        if get_time(self.to_time) <= get_time(self.from_time):
            frappe.throw(_("To Time must be after From Time."))

    def validate_no_overlap(self):
        """Two windows on the same day would make "is the trainer free" ambiguous."""
        filters = {
            "trainer": self.trainer,
            "day_of_week": self.day_of_week,
            "from_time": ["<", format_time(self.to_time)],
            "to_time": [">", format_time(self.from_time)],
        }
        if self.name:
            filters["name"] = ["!=", self.name]

        if frappe.db.exists("Trainer Availability", filters):
            frappe.throw(
                _("This trainer already has an availability window on {0} that overlaps.").format(
                    _(self.day_of_week)
                )
            )
