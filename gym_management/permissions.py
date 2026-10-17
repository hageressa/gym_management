"""Row-level rules for the Trainer role.

The brief gives trainers "read own sessions, mark attendance". The role
permissions on the DocTypes grant read on Class Session and read/write on
Class Booking; these hooks narrow that to the sessions the trainer teaches.
A trainer is matched through Employee.user_id, since Gym Trainer links to an
Employee. Anyone who also holds a manager or front desk role is not narrowed.
"""

import frappe

UNRESTRICTED_ROLES = {"System Manager", "Gym Manager", "Front Desk"}


def is_trainer_only(user):
    roles = set(frappe.get_roles(user))
    return "Trainer" in roles and not roles & UNRESTRICTED_ROLES


def get_trainer_for_user(user):
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
    if not employee:
        return None
    return frappe.db.get_value("Gym Trainer", {"employee": employee}, "name")


def class_session_query(user=None):
    """SQL condition added to every Class Session list a trainer opens."""
    user = user or frappe.session.user
    if not is_trainer_only(user):
        return ""

    trainer = get_trainer_for_user(user)
    if not trainer:
        return "1=0"
    return f"`tabClass Session`.`trainer` = {frappe.db.escape(trainer)}"


def class_booking_query(user=None):
    user = user or frappe.session.user
    if not is_trainer_only(user):
        return ""

    trainer = get_trainer_for_user(user)
    if not trainer:
        return "1=0"
    return (
        "`tabClass Booking`.`class_session` in "
        f"(select `name` from `tabClass Session` where `trainer` = {frappe.db.escape(trainer)})"
    )


def class_session_has_permission(doc, ptype=None, user=None):
    """The same rule for a single document opened directly."""
    user = user or frappe.session.user
    if not is_trainer_only(user):
        return True
    return bool(doc.trainer) and doc.trainer == get_trainer_for_user(user)


def class_booking_has_permission(doc, ptype=None, user=None):
    user = user or frappe.session.user
    if not is_trainer_only(user):
        return True

    trainer = frappe.db.get_value("Class Session", doc.class_session, "trainer")
    return bool(trainer) and trainer == get_trainer_for_user(user)
