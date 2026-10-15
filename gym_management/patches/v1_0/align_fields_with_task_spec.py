"""Move existing data onto the field names the task specification asks for.

Listed under ``post_model_sync`` so the new columns already exist when it runs.
Frappe leaves the old columns in place after a field is removed, which is what
lets this patch read them.
"""

import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
    rename_gym_class_defaults()
    split_session_datetimes()
    convert_status_to_is_active("Gym Room", active_value="Available")
    convert_status_to_is_active("Gym Trainer", active_value="Active")
    move_specialization_into_specialties()


def rename_gym_class_defaults():
    """trainer/room/capacity are defaults a session may override, so they are named so."""
    for old, new in (
        ("trainer", "default_trainer"),
        ("room", "default_room"),
        ("capacity", "default_capacity"),
    ):
        if frappe.db.has_column("Gym Class", old):
            rename_field("Gym Class", old, new)


def split_session_datetimes():
    """start_datetime/end_datetime became session_date + start_time + end_time."""
    if not frappe.db.has_column("Class Session", "start_datetime"):
        return

    frappe.db.sql(
        """
        UPDATE `tabClass Session`
        SET session_date = DATE(start_datetime),
            start_time = TIME(start_datetime),
            end_time = TIME(end_datetime)
        WHERE start_datetime IS NOT NULL
        """
    )


def convert_status_to_is_active(doctype, active_value):
    """A three-state Select became the Check the specification asks for."""
    if not frappe.db.has_column(doctype, "status"):
        return

    # doctype comes from this module's own call sites, never from user input.
    frappe.db.sql(
        f"UPDATE `tab{doctype}` SET is_active = CASE WHEN status = %s THEN 1 ELSE 0 END",
        active_value,
    )


def move_specialization_into_specialties():
    """The old free-text specialization becomes linked Gym Specialty rows."""
    if not frappe.db.has_column("Gym Trainer", "specialization"):
        return

    rows = frappe.db.sql(
        "SELECT name, specialization FROM `tabGym Trainer` WHERE IFNULL(specialization, '') != ''",
        as_dict=True,
    )

    for row in rows:
        trainer = frappe.get_doc("Gym Trainer", row.name)
        if trainer.specialties:
            continue

        for part in (piece.strip() for piece in row.specialization.split(",")):
            if not part:
                continue
            if not frappe.db.exists("Gym Specialty", part):
                frappe.get_doc(
                    {"doctype": "Gym Specialty", "specialty_name": part}
                ).insert(ignore_permissions=True)
            trainer.append("specialties", {"specialty": part})

        trainer.save(ignore_permissions=True)
