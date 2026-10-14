doc_events = {
    "Class Booking": {
        "before_save": "gym_management.events.set_booking_metadata",
        "after_insert": [
            "gym_management.events.update_session_booked_count",
            "gym_management.events.apply_booking_status_effects",
        ],
        "on_update": [
            "gym_management.events.update_session_booked_count",
            "gym_management.events.apply_booking_status_effects",
        ],
        "on_trash": "gym_management.events.update_session_booked_count",
    }
}