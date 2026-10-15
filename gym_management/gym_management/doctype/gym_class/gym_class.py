import frappe
from frappe import _
from frappe.model.document import Document


class GymClass(Document):
    def validate(self):
        self.validate_capacity_fits_room()

    def validate_capacity_fits_room(self):
        """The class default cannot promise more seats than its room holds."""
        if not self.default_room or not self.default_capacity:
            return

        room_capacity = frappe.db.get_value("Gym Room", self.default_room, "capacity")

        if room_capacity and int(self.default_capacity) > int(room_capacity):
            frappe.throw(
                _("Default capacity cannot exceed the capacity of {0} ({1}).").format(
                    self.default_room, room_capacity
                )
            )
