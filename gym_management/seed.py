"""Sample data for demos and manual testing.

Run it with:

    bench --site <site> execute gym_management.seed.run

It is safe to run more than once: every record is looked up before it is
created, so a second run only fills in what is missing.
"""

import frappe
from frappe.utils import add_days, add_to_date, now_datetime, today

from gym_management.utils import combine_date_time, format_time, get_default_company

ITEM_GROUP = "Gym Services"

SETTINGS = {
    "default_item_group": ITEM_GROUP,
    "cancellation_window_hours": 12,
    "enable_waitlist": 1,
    "no_show_limit": 3,
    "expiry_reminder_days": 7,
}

SPECIALTIES = ["Yoga", "HIIT", "Strength", "Cardio"]

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

# Gym Trainer requires a unique Employee, so each trainer gets one of their own.
TRAINERS = [
    {"trainer_name": "Ahmed Hassan", "specialties": ["Yoga"], "is_active": 1},
    {"trainer_name": "Mona Khaled", "specialties": ["HIIT", "Strength"], "is_active": 1},
]

ROOMS = [
    {"room_name": "Studio A", "capacity": 20, "location": "Ground floor", "is_active": 1},
    {"room_name": "Studio B", "capacity": 8, "location": "First floor", "is_active": 1},
]

CLASSES = [
    {
        "class_name": "Yoga Basics",
        "category": "Yoga",
        "trainer_name": "Ahmed Hassan",
        "room_name": "Studio A",
        "default_capacity": 12,
        "duration_minutes": 60,
    },
    {
        "class_name": "HIIT Express",
        "category": "HIIT",
        "trainer_name": "Mona Khaled",
        "room_name": "Studio B",
        # Deliberately small so the waitlist is easy to demonstrate.
        "default_capacity": 2,
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
    ("Yoga Basics", 0, 18),
    ("HIIT Express", 0, 20),
    ("Yoga Basics", 1, 18),
    ("HIIT Express", 1, 20),
    ("Yoga Basics", 3, 18),
    ("HIIT Express", 4, 20),
]


def run():
    """Create the sample gym data. Prints what it made."""
    ensure_item_group()
    ensure_settings()

    for specialty in SPECIALTIES:
        ensure_specialty(specialty)

    plans = [ensure_plan(values) for values in PLANS]
    trainers = {values["trainer_name"]: ensure_trainer(values) for values in TRAINERS}
    rooms = {values["room_name"]: ensure_room(values) for values in ROOMS}
    classes = {
        values["class_name"]: ensure_class(values, trainers, rooms) for values in CLASSES
    }
    members = [ensure_member(values) for values in MEMBERS]

    sessions = [ensure_session(name, day, hour, classes) for name, day, hour in SESSIONS]
    sessions = [name for name in sessions if name]

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


def ensure_specialty(name):
    if frappe.db.exists("Gym Specialty", name):
        return name

    frappe.get_doc({"doctype": "Gym Specialty", "specialty_name": name}).insert(
        ignore_permissions=True
    )
    return name


def ensure_plan(values):
    if frappe.db.exists("Membership Plan", values["plan_name"]):
        return values["plan_name"]

    plan = frappe.get_doc({"doctype": "Membership Plan", **values})
    plan.insert(ignore_permissions=True)
    return plan.name


def ensure_employee(full_name):
    """Gym Trainer links 1:1 to an Employee, so the seed needs one per trainer."""
    existing = frappe.db.get_value("Employee", {"employee_name": full_name})
    if existing:
        return existing

    company = get_default_company()
    if not company:
        frappe.throw("Set a default Company before seeding trainers.")

    first_name, _, last_name = full_name.partition(" ")

    employee = frappe.get_doc(
        {
            "doctype": "Employee",
            "first_name": first_name,
            "last_name": last_name,
            "gender": frappe.db.get_value("Gender", {"name": "Other"})
            or frappe.db.get_value("Gender", {}, "name"),
            "date_of_birth": "1990-01-01",
            "date_of_joining": today(),
            "company": company,
            "status": "Active",
        }
    )
    employee.insert(ignore_permissions=True)
    return employee.name


def ensure_trainer(values):
    employee = ensure_employee(values["trainer_name"])

    existing = frappe.db.get_value("Gym Trainer", {"employee": employee})
    if existing:
        return existing

    trainer = frappe.get_doc(
        {
            "doctype": "Gym Trainer",
            "employee": employee,
            "trainer_name": values["trainer_name"],
            "is_active": values["is_active"],
            "specialties": [{"specialty": name} for name in values["specialties"]],
        }
    )
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
            "default_trainer": trainers[values["trainer_name"]],
            "default_room": rooms[values["room_name"]],
            "default_capacity": values["default_capacity"],
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
    """One dated session of a class, ``days_ahead`` days from today at ``hour``."""
    gym_class_name = classes[class_name]
    gym_class = frappe.get_doc("Gym Class", gym_class_name)

    session_date = add_days(today(), days_ahead)
    start_time = f"{hour:02d}:00:00"
    start = combine_date_time(session_date, start_time)

    # A Scheduled session may not start in the past, so skip slots already gone.
    if start <= now_datetime():
        return None

    existing = frappe.db.get_value(
        "Class Session",
        {
            "gym_class": gym_class_name,
            "session_date": session_date,
            "start_time": start_time,
        },
    )
    if existing:
        return existing

    duration = gym_class.duration_minutes or 60

    session = frappe.get_doc(
        {
            "doctype": "Class Session",
            "gym_class": gym_class_name,
            "trainer": gym_class.default_trainer,
            "room": gym_class.default_room,
            "session_date": session_date,
            "start_time": start_time,
            "end_time": format_time(add_to_date(start, minutes=duration)),
            "capacity": gym_class.default_capacity,
            "status": "Scheduled",
        }
    )
    session.insert(ignore_permissions=True)
    return session.name
