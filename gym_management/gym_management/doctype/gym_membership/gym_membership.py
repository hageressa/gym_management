
import frappe
from frappe.model.document import Document
from frappe.utils import add_days, add_months, getdate


class GymMembership(Document):
    def validate(self):
        self.validate_freeze_history()
        self.calculate_end_date()

    def validate_freeze_history(self):
        if not self.membership_plan:
            return

        plan = frappe.get_doc("Membership Plan", self.membership_plan)
        max_freeze_days = int(getattr(plan, "max_freeze_days", 0) or 0)
        total_freeze_days = 0
        periods = []

        for row in self.get("freeze_history") or []:
            if not row.freeze_from or not row.freeze_to:
                frappe.throw("Freeze From and Freeze To are required.")

            freeze_from = getdate(row.freeze_from)
            freeze_to = getdate(row.freeze_to)

            if freeze_to <= freeze_from:
                frappe.throw("Freeze To must be after Freeze From.")

            row.days = (freeze_to - freeze_from).days + 1
            total_freeze_days += row.days
            periods.append((freeze_from, freeze_to))

        periods.sort(key=lambda period: period[0])
        for previous, current in zip(periods, periods[1:]):
            if current[0] <= previous[1]:
                frappe.throw("Membership freeze periods cannot overlap.")

        if total_freeze_days > max_freeze_days:
            frappe.throw(
                f"Total freeze days ({total_freeze_days}) exceed "
                f"the plan limit ({max_freeze_days})."
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

    def on_submit(self):
        # Do not recreate an invoice or overwrite a later membership status.
        if self.sales_invoice:
            return

        other_active = frappe.db.exists(
            "Gym Membership",
            {
                "member": self.member,
                "docstatus": 1,
                "status": "Active",
                "name": ["!=", self.name],
            },
        )
        if other_active:
            frappe.throw(
                "This member already has an active membership."
            )

        plan = frappe.get_doc(
            "Membership Plan", self.membership_plan
        )

        if not plan.item:
            frappe.throw(
                "The Membership Plan must have an Item before submission."
            )

        member = frappe.get_doc("Gym Member", self.member)

        if not member.customer:
            frappe.throw(
                "The Gym Member must be linked to a Customer before submission."
            )

        company = frappe.defaults.get_global_default("company")

        if not company:
            company = frappe.db.get_value(
                "Company", {"company_name": "Gym Co"}, "name"
            )

        if not company:
            frappe.throw("Set a default Company before submitting.")

        company_doc = frappe.get_doc("Company", company)
        price_list = "Standard Selling"

        price_list_currency = frappe.db.get_value(
            "Price List", price_list, "currency"
        )

        if not price_list_currency:
            frappe.throw("Standard Selling Price List is required.")

        if not company_doc.default_receivable_account:
            frappe.throw(
                "Set a Default Receivable Account in Company first."
            )

        settings = frappe.get_single("Gym Settings")
        income_account = (
            settings.default_income_account
            or company_doc.default_income_account
        )

        if not income_account or not company_doc.cost_center:
            frappe.throw(
                "Set the Default Income Account in Gym Settings or Company, "
                "and set the Cost Center in Company."
            )

        account_company = frappe.db.get_value(
            "Account", income_account, "company"
        )
        if account_company != company:
            frappe.throw(
                "The configured income account must belong to the selected Company."
            )

        invoice = frappe.get_doc({
            "doctype": "Sales Invoice",
            "naming_series": "ACC-SINV-.YYYY.-",
            "company": company,
            "posting_date": frappe.utils.today(),
            "customer": member.customer,
            "debit_to": company_doc.default_receivable_account,
            "currency": company_doc.default_currency,
            "conversion_rate": 1,
            "selling_price_list": price_list,
            "price_list_currency": price_list_currency,
            "plc_conversion_rate": 1,
            "items": [{
                "item_code": plan.item,
                "qty": 1,
                "rate": plan.price,
                "income_account": income_account,
                "cost_center": company_doc.cost_center,
            }],
        })

        invoice.insert(ignore_permissions=True)
        invoice.submit()

        self.db_set("sales_invoice", invoice.name)
        self.db_set("status", "Active")
    def on_cancel(self):
        if not self.sales_invoice:
            return

        invoice = frappe.get_doc(
            "Sales Invoice", self.sales_invoice
        )

        if invoice.docstatus == 1:
            invoice.cancel()