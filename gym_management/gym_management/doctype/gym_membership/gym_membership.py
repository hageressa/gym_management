
from itertools import pairwise

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_months, getdate, today

from gym_management.utils import (
    get_default_company,
    get_selling_price_list,
    sync_member_active_membership,
)


class GymMembership(Document):
    def validate(self):
        self.validate_plan_is_active()
        self.validate_freeze_history()
        self.calculate_end_date()
        self.set_class_pack_balance()

    def validate_plan_is_active(self):
        """A plan switched off may not be sold; memberships already submitted keep it."""
        if self.docstatus != 0 or not self.membership_plan:
            return
        if not frappe.db.get_value("Membership Plan", self.membership_plan, "is_active"):
            frappe.throw(_("Membership Plan {0} is not active.").format(self.membership_plan))

    def validate_freeze_history(self):
        if not self.membership_plan:
            return

        plan = frappe.get_doc("Membership Plan", self.membership_plan)
        max_freeze_days = int(getattr(plan, "max_freeze_days", 0) or 0)
        total_freeze_days = 0
        periods = []

        for row in self.get("freeze_history") or []:
            if not row.freeze_from or not row.freeze_to:
                frappe.throw(_("Freeze From and Freeze To are required."))

            freeze_from = getdate(row.freeze_from)
            freeze_to = getdate(row.freeze_to)

            if freeze_to <= freeze_from:
                frappe.throw(_("Freeze To must be after Freeze From."))

            row.days = (freeze_to - freeze_from).days + 1
            total_freeze_days += row.days
            periods.append((freeze_from, freeze_to))

        periods.sort(key=lambda period: period[0])
        for previous, current in pairwise(periods):
            if current[0] <= previous[1]:
                frappe.throw(_("Membership freeze periods cannot overlap."))

        if total_freeze_days > max_freeze_days:
            frappe.throw(
                _("Total freeze days ({0}) exceed the plan limit ({1}).").format(
                    total_freeze_days, max_freeze_days
                )
            )

    def calculate_end_date(self):
        if not self.start_date or not self.membership_plan:
            return

        plan = frappe.get_doc("Membership Plan", self.membership_plan)

        if plan.duration_type == "Days":
            base_end_date = add_days(
                getdate(self.start_date), plan.duration_value
            )
        elif plan.duration_type == "Months":
            base_end_date = add_months(
                getdate(self.start_date), plan.duration_value
            )
        else:
            self.end_date = None
            return

        total_freeze_days = sum(
            (getdate(row.freeze_to) - getdate(row.freeze_from)).days + 1
            for row in (self.get("freeze_history") or [])
            if row.freeze_from and row.freeze_to
        )
        self.end_date = add_days(base_end_date, total_freeze_days)

    def set_class_pack_balance(self):
        """Give a new membership its class allowance: a class pack, or any plan
        whose classes_included is set (0 means unlimited)."""
        if not self.is_new() or self.classes_remaining or not self.membership_plan:
            return

        plan = frappe.get_doc("Membership Plan", self.membership_plan)
        if plan.duration_type == "Class Pack":
            self.classes_remaining = plan.classes_included or plan.duration_value
        elif plan.classes_included:
            self.classes_remaining = plan.classes_included

    def before_submit(self):
        self.validate_single_active_membership()

    def validate_single_active_membership(self):
        """A member may hold only one Active membership at a time.

        A Frozen one counts too: it becomes Active again when the freeze ends.
        """
        if frappe.db.exists(
            "Gym Membership",
            {
                "member": self.member,
                "docstatus": 1,
                "status": ["in", ["Active", "Frozen"]],
                "name": ["!=", self.name],
            },
        ):
            frappe.throw(_("This member already has an active membership."))

    def on_submit(self):
        """Create the Sales Invoice once, then activate the membership."""
        # Idempotency: never create a second invoice if submit is retried.
        if self.sales_invoice:
            return

        invoice = self.create_sales_invoice()
        self.db_set("sales_invoice", invoice.name)
        self.db_set("status", "Active")
        sync_member_active_membership(self.member)

    def create_sales_invoice(self):
        """Build and submit the Sales Invoice for the plan Item."""
        plan = frappe.get_doc("Membership Plan", self.membership_plan)
        if not plan.item:
            frappe.throw(_("The Membership Plan must have an Item before submission."))

        customer = self.get_member_customer()
        company_doc = self.get_billing_company()
        price_list, price_list_currency = self.get_price_list()
        income_account = self.get_income_account(company_doc)

        invoice = frappe.get_doc(
            {
                "doctype": "Sales Invoice",
                "company": company_doc.name,
                "posting_date": today(),
                "customer": customer,
                "debit_to": company_doc.default_receivable_account,
                "currency": company_doc.default_currency,
                "conversion_rate": 1,
                "selling_price_list": price_list,
                "price_list_currency": price_list_currency,
                "plc_conversion_rate": 1,
                "items": [
                    {
                        "item_code": plan.item,
                        "qty": 1,
                        "rate": plan.price,
                        "income_account": income_account,
                        "cost_center": company_doc.cost_center,
                    }
                ],
            }
        )
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        return invoice

    def get_member_customer(self):
        customer = frappe.db.get_value("Gym Member", self.member, "customer")
        if not customer:
            frappe.throw(_("The Gym Member must be linked to a Customer before submission."))
        return customer

    def get_billing_company(self):
        company = get_default_company()
        if not company:
            frappe.throw(_("Set a default Company before submitting."))

        company_doc = frappe.get_doc("Company", company)
        if not company_doc.default_receivable_account:
            frappe.throw(_("Set a Default Receivable Account in Company first."))
        return company_doc

    def get_price_list(self):
        price_list = get_selling_price_list()
        currency = frappe.db.get_value("Price List", price_list, "currency") if price_list else None
        if not currency:
            frappe.throw(_("An enabled selling Price List is required."))
        return price_list, currency

    def get_income_account(self, company_doc):
        """Gym Settings income account first, then the Company default."""
        settings = frappe.get_single("Gym Settings")
        income_account = settings.default_income_account or company_doc.default_income_account

        if not income_account or not company_doc.cost_center:
            frappe.throw(
                _(
                    "Set the Default Income Account in Gym Settings or Company, "
                    "and set the Cost Center in Company."
                )
            )

        if frappe.db.get_value("Account", income_account, "company") != company_doc.name:
            frappe.throw(_("The configured income account must belong to the selected Company."))
        return income_account

    def on_cancel(self):
        self.db_set("status", "Cancelled")
        sync_member_active_membership(self.member)

        if not self.sales_invoice:
            return

        invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
        if invoice.docstatus == 1:
            invoice.cancel()
