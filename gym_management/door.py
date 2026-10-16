"""Door-access integration.

A card reader at the gym door is not a Frappe user and cannot log in, so it
calls one guest endpoint with a shared token and gets back a plain yes/no plus
the reason — which is all a small display beside the door needs to show.

The decision itself is not re-implemented here: it comes from
``get_membership_block_reason``, the same rule the front desk and the booking
validations use. A member refused at the desk is refused at the door, always.
"""

import hmac

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import today

from gym_management.utils import get_latest_membership, get_membership_block_reason

REJECTED_LOG_TITLE = "Gym door access rejected"


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=60, seconds=60)
def door_access(member, token):
    """Decide whether the door opens for this member, and record the entry.

    Called by the reader as:
        POST /api/method/gym_management.door.door_access
        {"member": "MEM-0003", "token": "<shared token>"}
    """
    verify_door_token(token)

    membership_name = get_latest_membership(member)
    if not membership_name:
        return refuse(member, _("no membership on file"))

    membership = frappe.get_doc("Gym Membership", membership_name)

    reason = get_membership_block_reason(membership, today())
    if reason:
        return refuse(member, reason)

    # The token is the authorisation here: Guest holds no permission on
    # Gym Check In, and must not be given any.
    check_in = frappe.get_doc(
        {
            "doctype": "Gym Check In",
            "member": member,
            "membership": membership.name,
            "method": "Card",
        }
    )
    check_in.insert(ignore_permissions=True)

    return {
        "open": True,
        "member": member,
        "member_name": get_member_name(member),
        "membership": membership.name,
        "check_in": check_in.name,
    }


def verify_door_token(token):
    """Reject anything that is not the token configured in Gym Settings.

    ``hmac.compare_digest`` takes the same time whatever the input, so the
    token cannot be recovered one character at a time by timing the replies.
    """
    expected = frappe.get_single("Gym Settings").get_password(
        "door_access_token", raise_exception=False
    )

    if not expected:
        frappe.throw(_("Door access is not configured."), frappe.PermissionError)

    if not token or not hmac.compare_digest(str(token), str(expected)):
        frappe.log_error(
            title=REJECTED_LOG_TITLE,
            message="A door request arrived with an invalid token.",
        )
        frappe.throw(_("Invalid door token."), frappe.PermissionError)


def refuse(member, reason):
    """A refusal carries the reason so the door display can explain itself."""
    return {
        "open": False,
        "member": member,
        "member_name": get_member_name(member),
        "reason": reason,
    }


def get_member_name(member):
    return frappe.db.get_value("Gym Member", member, "member_name")
