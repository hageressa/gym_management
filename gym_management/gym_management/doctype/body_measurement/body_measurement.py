import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

# Optional measurements. An empty Float is stored as 0, so 0 means "not taken"
# and only a negative value is rejected.
OPTIONAL_MEASUREMENTS = {
    "height_cm": "Height (cm)",
    "body_fat_percent": "Body Fat %",
    "chest_cm": "Chest (cm)",
    "waist_cm": "Waist (cm)",
    "hips_cm": "Hips (cm)",
}


class BodyMeasurement(Document):
    def validate(self):
        self.validate_date()
        self.validate_values()
        self.set_bmi()

    def validate_date(self):
        if getdate(self.measurement_date) > getdate(today()):
            frappe.throw(_("A measurement cannot be dated in the future."))

    def validate_values(self):
        if flt(self.weight_kg) <= 0:
            frappe.throw(_("Weight must be greater than zero."))

        for fieldname, label in OPTIONAL_MEASUREMENTS.items():
            if flt(self.get(fieldname)) < 0:
                frappe.throw(_("{0} cannot be negative.").format(_(label)))

        if flt(self.body_fat_percent) > 100:
            frappe.throw(_("Body fat cannot be more than 100%."))

    def set_bmi(self):
        """BMI = weight (kg) / height (m) squared. Left empty without a height."""
        if flt(self.height_cm) <= 0:
            self.bmi = None
            return

        height_m = flt(self.height_cm) / 100
        self.bmi = flt(flt(self.weight_kg) / (height_m * height_m), 1)
