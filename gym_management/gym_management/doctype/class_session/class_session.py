import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, now_datetime

from gym_management.utils import combine_date_time, format_time


class ClassSession(Document):
    def validate(self):
        self.set_defaults_from_class()
        self.set_end_time()
        self.validate_time_range()
        self.validate_not_in_the_past()
        self.validate_class_and_capacity()
        self.validate_room_and_trainer_availability()
        self.validate_no_overlaps()

    def set_defaults_from_class(self):
        """Trainer, room and capacity default from the class template."""
        if not self.gym_class:
            return

        defaults = frappe.db.get_value(
            "Gym Class",
            self.gym_class,
            ["default_trainer", "default_room", "default_capacity"],
            as_dict=True,
        )
        if not defaults:
            return

        if not self.trainer:
            self.trainer = defaults.default_trainer
        if not self.room:
            self.room = defaults.default_room
        if not self.capacity:
            self.capacity = defaults.default_capacity

    def get_start(self):
        """The session's start as a datetime, for comparing against 'now'."""
        return combine_date_time(self.session_date, self.start_time)

    def get_end(self):
        return combine_date_time(self.session_date, self.end_time)

    def set_end_time(self):
        """Derive end_time from the class duration, always.

        Frappe fills an empty Time field with the current time when a document
        is created, so "only compute when blank" would silently keep that
        value. The end of a session follows from its class, so it is computed
        every save and the field is read-only on the form.
        """
        if not self.session_date or not self.start_time or not self.gym_class:
            return

        duration = frappe.db.get_value("Gym Class", self.gym_class, "duration_minutes") or 60
        self.end_time = format_time(add_to_date(self.get_start(), minutes=int(duration)))

    def validate_time_range(self):
        if not self.session_date or not self.start_time or not self.end_time:
            frappe.throw(_("Session date, start time and end time are required."))

        if self.get_end() <= self.get_start():
            frappe.throw(_("End time must be after start time."))

    def validate_not_in_the_past(self):
        """Refuse a past start only when the timing is being set or moved.

        Editing an unrelated field on yesterday's session must still save.
        """
        if self.status != "Scheduled":
            return

        if not self.is_new() and not (
            self.has_value_changed("session_date") or self.has_value_changed("start_time")
        ):
            return

        if self.get_start() < now_datetime():
            frappe.throw(_("A scheduled class session cannot start in the past."))

    def validate_class_and_capacity(self):
        if not self.gym_class:
            frappe.throw(_("Please select a Gym Class."))

        gym_class = frappe.get_doc("Gym Class", self.gym_class)

        if gym_class.status != "Active":
            frappe.throw(_("Only active gym classes can be scheduled."))

        if not self.capacity or int(self.capacity) < 1:
            self.capacity = gym_class.default_capacity

        if not self.capacity or int(self.capacity) < 1:
            frappe.throw(_("Session capacity must be greater than zero."))

        if self.capacity > gym_class.default_capacity:
            frappe.throw(_("Session capacity cannot exceed the class capacity."))

    def validate_room_and_trainer_availability(self):
        if self.room:
            room = frappe.get_doc("Gym Room", self.room)
            if not room.is_active:
                frappe.throw(_("The selected room is not active."))
            if self.capacity and room.capacity and self.capacity > room.capacity:
                frappe.throw(_("Session capacity cannot exceed the room capacity."))

        if self.trainer:
            trainer = frappe.get_doc("Gym Trainer", self.trainer)
            if not trainer.is_active:
                frappe.throw(_("The selected trainer is not active."))

    def validate_no_overlaps(self):
        """No trainer or room may hold two scheduled sessions at once.

        A session runs inside one day, so comparing times within the same
        session_date is enough and keeps the query on indexed columns.
        """
        for fieldname, value, label in (
            ("trainer", self.trainer, _("trainer")),
            ("room", self.room, _("room")),
        ):
            if not value:
                continue

            filters = {
                fieldname: value,
                "status": "Scheduled",
                "session_date": self.session_date,
                "start_time": ["<", format_time(self.end_time)],
                "end_time": [">", format_time(self.start_time)],
            }

            if self.name:
                filters["name"] = ["!=", self.name]

            if frappe.db.exists("Class Session", filters):
                frappe.throw(
                    _("The selected {0} already has a session during this time.").format(label)
                )
