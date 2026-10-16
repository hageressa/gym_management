import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, cint, formatdate, get_time, getdate, now_datetime

from gym_management.utils import combine_date_time, format_time, get_valid_membership


class PersonalTrainingSession(Document):
    def validate(self):
        self.set_end_time()
        self.validate_time_range()

        # Completing or cancelling a session must always save, even if the
        # membership has lapsed since; the booking rules guard Scheduled only.
        if self.status != "Scheduled":
            return

        self.validate_not_in_the_past()
        self.validate_membership()
        self.validate_trainer_is_active()
        self.validate_within_availability()
        self.validate_no_trainer_conflict()
        self.validate_no_member_conflict()

    def get_start(self):
        return combine_date_time(self.session_date, self.start_time)

    def set_end_time(self):
        """Always computed: Frappe pre-fills an empty Time field with the
        current time, the same reason as Class Session end_time."""
        if cint(self.duration_minutes) <= 0:
            frappe.throw(_("Duration must be greater than zero."))

        self.end_time = format_time(add_to_date(self.get_start(), minutes=cint(self.duration_minutes)))

    def validate_time_range(self):
        """A session that runs past midnight would wrap to an earlier end time."""
        if get_time(self.end_time) <= get_time(self.start_time):
            frappe.throw(_("A personal training session must end on the same day."))

    def validate_not_in_the_past(self):
        if not self.is_new() and not (
            self.has_value_changed("session_date") or self.has_value_changed("start_time")
        ):
            return

        if self.get_start() < now_datetime():
            frappe.throw(_("A personal training session cannot start in the past."))

    def validate_membership(self):
        """Same rule as class bookings and check-ins, judged on the session date."""
        membership = get_valid_membership(self.member, self.session_date)
        if not membership:
            frappe.throw(
                _("{0} has no membership that is valid on {1}.").format(
                    self.member_name or self.member, formatdate(self.session_date)
                )
            )
        self.membership = membership

    def validate_trainer_is_active(self):
        if not frappe.db.get_value("Gym Trainer", self.trainer, "is_active"):
            frappe.throw(_("The selected trainer is not active."))

    def validate_within_availability(self):
        """The whole session must fit inside one of the trainer's windows that day."""
        weekday = getdate(self.session_date).strftime("%A")
        windows = frappe.get_all(
            "Trainer Availability",
            filters={"trainer": self.trainer, "day_of_week": weekday},
            fields=["from_time", "to_time"],
        )

        start, end = get_time(self.start_time), get_time(self.end_time)
        if not any(get_time(w.from_time) <= start and end <= get_time(w.to_time) for w in windows):
            frappe.throw(
                _("The trainer is not available on {0} from {1} to {2}.").format(
                    _(weekday), format_time(start)[:5], format_time(end)[:5]
                )
            )

    def overlapping(self, **filters):
        """Filters for Scheduled rows on the same date whose times overlap this one."""
        filters.update(
            {
                "status": "Scheduled",
                "session_date": self.session_date,
                "start_time": ["<", format_time(self.end_time)],
                "end_time": [">", format_time(self.start_time)],
            }
        )
        return filters

    def validate_no_trainer_conflict(self):
        """A trainer cannot be in two places: another 1:1 or a group class."""
        others = self.overlapping(trainer=self.trainer, name=["!=", self.name])
        if frappe.db.exists("Personal Training Session", others):
            frappe.throw(_("The trainer already has a personal training session at this time."))

        if frappe.db.exists("Class Session", self.overlapping(trainer=self.trainer)):
            frappe.throw(_("The trainer is teaching a class at this time."))

    def validate_no_member_conflict(self):
        others = self.overlapping(member=self.member, name=["!=", self.name])
        if frappe.db.exists("Personal Training Session", others):
            frappe.throw(_("This member already has a personal training session at this time."))
