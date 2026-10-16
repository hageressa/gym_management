from frappe import _


def get_data():
    """Connections shown on the Gym Trainer form, all linked by the trainer field."""
    return {
        "fieldname": "trainer",
        "transactions": [
            {"label": _("Schedule"), "items": ["Trainer Availability", "Class Session"]},
            {"label": _("Clients"), "items": ["Personal Training Session", "Workout Plan"]},
        ],
    }
