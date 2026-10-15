"""Sample data for demos and manual testing.

Run it with:

    bench --site <site> execute gym_management.seed.run

It is safe to run more than once: every record is looked up before it is
created, so a second run only fills in what is missing.
"""

import frappe
from frappe.utils import add_days, add_to_date, getdate, today

ITEM_GROUP = "Gym Services"

SETTINGS = {
    "default_item_group": ITEM_GROUP,
    "cancellation_window_hours": 12,
    "enable_waitlist": 1,
    "no_show_limit": 3,
    "expiry_reminder_days": 7,
}

PLANS = [
    {
        "plan_name": "Monthly Unlimited",
        "duration_type": "Months",
        "duration_value": 1,
        "price": 800,
        "classes_included": 0,
        "max_freeze_days": 7,
        "is_active": 1,
    },
    {
        "plan_name": "Quarterly Unlimited",
        "duration_type": "Months",
        "duration_value": 3,
        "price": 2100,
        "classes_included": 0,
        "max_freeze_days": 21,
        "is_active": 1,
    },
    {
        "plan_name": "10 Class Pack",
        "duration_type": "Class Pack",
        "duration_value": 10,
        "price": 600,
        "classes_included": 10,
        "max_freeze_days": 0,
        "is_active": 1,
    },
]

TRAINERS = [
    {"trainer_name": "Coach Ahmed", "specialization": "Yoga", "status": "Active"},
    {"trainer_name": "Coach Mona", "specialization": "HIIT, Strength", "status": "Active"},
]

ROOMS = [
    {"room_name": "Studio A", "capacity": 20, "location": "Ground floor", "status": "Available"},
    {"room_name": "Studio B", "capacity": 8, "location": "First floor", "status": "Available"},
]

CLASSES = [
    {
        "class_name": "Yoga Basics",
        "category": "Yoga",
        "trainer_name": "Coach Ahmed",
        "room_name": "Studio A",
        "capacity": 12,
        "duration_minutes": 60,
    },
    {
        "class_name": "HIIT Express",
        "category": "HIIT",
        "trainer_name": "Coach Mona",
        "room_name": "Studio B",
        # Deliberately small so the waitlist is easy to demonstrate.
        "capacity": 2,
        "duration_minutes": 45,
    },
]

MEMBERS = [
    {"member_name": "Nour Hassan", "email": "nour@example.com", "phone": "01000000001"},
    {"member_name": "Omar Fathy", "email": "omar@example.com", "phone": "01000000002"},
    {"member_name": "Salma Adel", "email": "salma@example.com", "phone": "01000000003"},
]

# (class name, days from today, hour) — kept apart so no trainer or room overlaps.
SESSIONS = [
    ("Yoga Basics", 1, 18),
    ("Yoga Basics", 3, 18),
    ("HIIT Express", 1, 20),
    ("HIIT Express", 4, 20),
]


def run():
    """Create the sample gym data. Prints what it made."""
    ensure_item_group()
    ensure_settings()

    plans = [ensure_plan(values) for values in PLANS]
    trainers = {values["trainer_name"]: ensure_trainer(values) for values in TRAINERS}
    rooms = {values["room_name"]: ensure_room(values) for values in ROOMS}
    classes = {
        values["class_name"]: ensure_class(values, trainers, rooms) for values in CLASSES
    }
    members = [ensure_member(values) for values in MEMBERS]
    sessions = [ensure_session(name, day, hour, classes) for name, day, hour in SESSIONS]

    frappe.db.commit()

    print(f"Plans:    {len(plans)}")
    print(f"Trainers: {len(trainers)}")
    print(f"Rooms:    {len(rooms)}")
    print(f"Classes:  {len(classes)}")
    print(f"Members:  {len(members)}")
    print(f"Sessions: {len(sessions)}")
    print("\nNext: open a Gym Member, create a Gym Membership and submit it.")


def ensure_item_group():
    """A non-group Item Group for the auto-created plan Items."""
    if frappe.db.exists("Item Group", ITEM_GROUP):
        return ITEM_GROUP

    frappe.get_doc(
        {
            "doctype": "Item Group",
            "item_group_name": ITEM_GROUP,
            "parent_item_group": "All Item Groups",
            "is_group": 0,
        }
    ).insert(ignore_permissions=True)
    return ITEM_GROUP


def ensure_settings():
    settings = frappe.get_single("Gym Settings")
    for field, value in SETTINGS.items():
        if not settings.get(field):
            settings.set(field, value)
    settings.save(ignore_permissions=True)


def ensure_plan(values):
    if frappe.db.exists("Membership Plan", values["plan_name"]):
        return values["plan_name"]

    plan = frappe.get_doc({"doctype": "Membership Plan", **values})
    plan.insert(ignore_permissions=True)
    return plan.name


def ensure_trainer(values):
    existing = frappe.db.get_value("Gym Trainer", {"trainer_name": values["trainer_name"]})
    if existing:
        return existing

    trainer = frappe.get_doc({"doctype": "Gym Trainer", **values})
    # Link an Employee when the site has one; the field stays empty otherwise.
    trainer.employee = frappe.db.get_value("Employee", {"status": "Active"}, "name")
    trainer.insert(ignore_permissions=True)
    return trainer.name


def ensure_room(values):
    existing = frappe.db.get_value("Gym Room", {"room_name": values["room_name"]})
    if existing:
        return existing

    room = frappe.get_doc({"doctype": "Gym Room", **values})
    room.insert(ignore_permissions=True)
    return room.name


def ensure_class(values, trainers, rooms):
    existing = frappe.db.get_value("Gym Class", {"class_name": values["class_name"]})
    if existing:
        return existing

    gym_class = frappe.get_doc(
        {
            "doctype": "Gym Class",
            "class_name": values["class_name"],
            "category": values["category"],
            "trainer": trainers[values["trainer_name"]],
            "room": rooms[values["room_name"]],
            "capacity": values["capacity"],
            "duration_minutes": values["duration_minutes"],
            "status": "Active",
        }
    )
    gym_class.insert(ignore_permissions=True)
    return gym_class.name


def ensure_member(values):
    existing = frappe.db.get_value("Gym Member", {"member_name": values["member_name"]})
    if existing:
        return existing

    member = frappe.get_doc(
        {
            "doctype": "Gym Member",
            "status": "Active",
            "joined_on": today(),
            **values,
        }
    )
    member.insert(ignore_permissions=True)
    return member.name


def ensure_session(class_name, days_ahead, hour, classes):
    """One dated session of a class, starting ``days_ahead`` days from today."""
    gym_class_name = classes[class_name]
    gym_class = frappe.get_doc("Gym Class", gym_class_name)

    start = add_to_date(getdate(add_days(today(), days_ahead)), hours=hour)

    existing = frappe.db.get_value(
        "Class Session",
        {"gym_class": gym_class_name, "start_datetime": start},
    )
    if existing:
        return existing

    session = frappe.get_doc(
        {
            "doctype": "Class Session",
            "gym_class": gym_class_name,
            "trainer": gym_class.trainer,
            "room": gym_class.room,
            "start_datetime": start,
            "end_datetime": add_to_date(start, minutes=gym_class.duration_minutes or 60),
            "capacity": gym_class.capacity,
            "status": "Scheduled",
        }
    )
    session.insert(ignore_permissions=True)
    return session.name