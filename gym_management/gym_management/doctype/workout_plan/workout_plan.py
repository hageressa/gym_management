import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

# Each of these describes an amount, so a negative value is a typing mistake.
EXERCISE_AMOUNTS = {"sets": "Sets", "reps": "Reps", "weight_kg": "Weight (kg)"}


class WorkoutPlan(Document):
    def validate(self):
        self.validate_dates()
        self.validate_exercises()

    def validate_dates(self):
        if self.end_date and getdate(self.end_date) < getdate(self.start_date):
            frappe.throw(_("End date cannot be before the start date."))

    def validate_exercises(self):
        for row in self.exercises:
            for fieldname, label in EXERCISE_AMOUNTS.items():
                if flt(row.get(fieldname)) < 0:
                    frappe.throw(
                        _("Row {0}: {1} cannot be negative.").format(row.idx, _(label))
                    )
