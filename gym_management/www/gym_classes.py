import frappe
from frappe import _

from gym_management.portal import get_portal_context, get_portal_member

no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/gym-classes"
        raise frappe.Redirect

    context.title = _("Gym Classes")
    context.member = get_portal_member()
    if context.member:
        context.update(get_portal_context(context.member))
