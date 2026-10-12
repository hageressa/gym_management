import frappe
from frappe.utils import add_days, getdate, today


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = [
        {
            "label": "Membership",
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Gym Membership",
            "width": 160,
        },
        {
            "label": "Member",
            "fieldname": "member",
            "fieldtype": "Link",
            "options": "Gym Member",
            "width": 160,
        },
        {
            "label": "Plan",
            "fieldname": "membership_plan",
            "fieldtype": "Link",
            "options": "Membership Plan",
            "width": 150,
        },
        {
            "label": "Status",
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "label": "Start Date",
            "fieldname": "start_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": "End Date",
            "fieldname": "end_date",
            "fieldtype": "Date",
            "width": 110,
        },
        {
            "label": "Days Remaining",
            "fieldname": "days_remaining",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": "Sales Invoice",
            "fieldname": "sales_invoice",
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 160,
        },
    ]

    conditions = ["docstatus = 1", "end_date IS NOT NULL"]
    values = {}

    if filters.get("status"):
        conditions.append("status = %(status)s")
        values["status"] = filters.status

    if filters.get("days") is not None and filters.get("days") != "":
        days = max(int(filters.days), 0)
        conditions.append("end_date <= %(end_date)s")
        values["end_date"] = add_days(today(), days)

    rows = frappe.db.sql(
        f"""
        SELECT name, member, membership_plan, status,
               start_date, end_date, sales_invoice
        FROM `tabGym Membership`
        WHERE {" AND ".join(conditions)}
        ORDER BY end_date ASC
        """,
        values,
        as_dict=True,
    )

    today_date = getdate(today())
    for row in rows:
        row.days_remaining = (getdate(row.end_date) - today_date).days

    return columns, rows
