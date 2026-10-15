import unittest
from unittest.mock import patch

from gym_management.gym_management.doctype.gym_class.gym_class import GymClass

MODULE = "gym_management.gym_management.doctype.gym_class.gym_class"


def make_class(**values):
    defaults = {
        "doctype": "Gym Class",
        "class_name": "Yoga Basics",
        "default_room": "ROOM-0001",
        "default_capacity": 10,
    }
    defaults.update(values)
    return GymClass(defaults)


class TestGymClassCapacity(unittest.TestCase):
    @patch(f"{MODULE}.frappe.db.get_value", return_value=8)
    def test_rejects_a_default_capacity_above_the_room(self, get_value):
        gym_class = make_class(default_capacity=10)

        with self.assertRaises(Exception):
            gym_class.validate_capacity_fits_room()

    @patch(f"{MODULE}.frappe.db.get_value", return_value=20)
    def test_allows_a_default_capacity_the_room_can_hold(self, get_value):
        gym_class = make_class(default_capacity=10)

        gym_class.validate_capacity_fits_room()

    @patch(f"{MODULE}.frappe.db.get_value")
    def test_skips_the_check_when_no_room_is_set(self, get_value):
        gym_class = make_class(default_room=None)

        gym_class.validate_capacity_fits_room()

        get_value.assert_not_called()
