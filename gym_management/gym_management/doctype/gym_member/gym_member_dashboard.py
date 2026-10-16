from frappe import _


def get_data():
    """Connections shown on the Gym Member form, all linked by the member field."""
    return {
        "fieldname": "member",
        "transactions": [
            {"label": _("Membership"), "items": ["Gym Membership", "Gym Check In"]},
            {"label": _("Classes"), "items": ["Class Booking"]},
            {"label": _("Progress"), "items": ["Workout Plan", "Body Measurement"]},
        ],
    }
