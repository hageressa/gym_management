import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, now_datetime


class ClassSession(Document):
    def validate(self):
        self.set_end_datetime()
        self.validate_time_range()
        self.validate_class_and_capacity()
        self.validate_room_and_trainer_availability()
        self.validate_no_overlaps()

    def set_end_datetime(self):
        if not self.start_datetime or not self.gym_class:
            return
        if self.end_datetime:
            return
        duration = frappe.db.get_value(
            "Gym Class", self.gym_class, "duration_minutes"
        ) or 60
        self.end_datetime = add_to_date(
            get_datetime(self.start_datetime), minutes=int(duration)
        )

    def validate_time_range(self):
        if not self.start_datetime or not self.end_datetime:
            frappe.throw("Start and end datetime are required.")
        start = get_datetime(self.start_datetime)
        end = get_datetime(self.end_datetime)
        if end <= start:
            frappe.throw("End datetime must be after start datetime.")
        if start < now_datetime() and self.status == "Scheduled":
            frappe.throw("A scheduled class session cannot start in the past.")

    def validate_class_and_capacity(self):
        if not self.gym_class:
            frappe.throw("Please select a Gym Class.")
        gym_class = frappe.get_doc("Gym Class", self.gym_class)
        if gym_class.status != "Active":
            frappe.throw("Only active gym classes can be scheduled.")
        if not self.capacity or int(self.capacity) < 1:
            self.capacity = gym_class.capacity
        if not self.capacity or int(self.capacity) < 1:
            frappe.throw("Session capacity must be greater than zero.")
        if self.capacity > gym_class.capacity:
            frappe.throw("Session capacity cannot exceed the class capacity.")

    def validate_room_and_trainer_availability(self):
        if self.room:
            room = frappe.get_doc("Gym Room", self.room)
            if room.status != "Available":
                frappe.throw("The selected room is not available.")
            if self.capacity and room.capacity and self.capacity > room.capacity:
                frappe.throw("Session capacity cannot exceed the room capacity.")
        if self.trainer:
            trainer = frappe.get_doc("Gym Trainer", self.trainer)
            if trainer.status != "Active":
                frappe.throw("The selected trainer is not active.")

    def validate_no_overlaps(self):
        start = get_datetime(self.start_datetime)
        end = get_datetime(self.end_datetime)
        for fieldname, value, label in (
            ("trainer", self.trainer, "trainer"),
            ("room", self.room, "room"),
        ):
            if not value:
                continue
            filters = {
                fieldname: value,
                "status": "Scheduled",
                "start_datetime": ["<", end],
                "end_datetime": [">", start],
            }
            if self.name:
                filters["name"] = ["!=", self.name]
            if frappe.db.exists("Class Session", filters):
                frappe.throw(
                    f"The selected {label} already has a session during this time."
                )
