import frappe
from frappe.utils import add_days, getdate, today


@frappe.whitelist()
def book_class(session, member):
    if not session or not member:
        frappe.throw("Session and member are required.")

    booking = frappe.get_doc({
        "doctype": "Class Booking",
        "class_session": session,
        "member": member,
        "booking_date": today(),
        "status": "Booked",
    })

    booking.insert()
    return {
        "booking": booking.name,
        "status": booking.status,
        "waitlist_position": booking.waitlist_position,
    }


@frappe.whitelist()
def get_available_sessions(date_from, date_to):
    start_date = getdate(date_from)
    end_date = getdate(date_to)

    if end_date < start_date:
        frappe.throw("End date cannot be before start date.")

    sessions = frappe.get_all(
        "Class Session",
        filters={
            "status": "Scheduled",
            "start_datetime": [
                "between",
                [
                    f"{start_date} 00:00:00",
                    f"{add_days(end_date, 1)} 00:00:00",
                ],
            ],
        },
        fields=[
            "name",
            "gym_class",
            "trainer",
            "room",
            "start_datetime",
            "end_datetime",
            "capacity",
            "status",
        ],
        order_by="start_datetime asc",
    )

    available_sessions = []

    for session in sessions:
        booked = frappe.db.count(
            "Class Booking",
            {
                "class_session": session.name,
                "status": ["in", ["Booked", "Attended"]],
            },
        )

        capacity = session.capacity or 0
        available_spots = max(capacity - booked, 0)

        if available_spots > 0:
            session["available_spots"] = available_spots
            available_sessions.append(session)

    return available_sessions
