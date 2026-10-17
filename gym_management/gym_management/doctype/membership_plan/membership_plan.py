import frappe
from frappe import _
from frappe.model.document import Document

from gym_management.utils import get_selling_price_list


class MembershipPlan(Document):
    def before_validate(self):
        self.create_service_item_if_missing()

    def validate(self):
        self.validate_unique_plan_name()

    def validate_unique_plan_name(self):
        if not self.plan_name:
            return

        filters = {"plan_name": self.plan_name}

        if not self.is_new():
            filters["name"] = ["!=", self.name]

        existing = frappe.db.get_value(
            "Membership Plan", filters, "name"
        )

        if existing:
            frappe.throw(_("Plan Name must be unique."))

    def create_service_item_if_missing(self):
        if self.item or not self.plan_name:
            return

        settings = frappe.get_single("Gym Settings")
        item_group = settings.default_item_group

        if not item_group:
            frappe.throw(_("Set Default Item Group in Gym Settings first."))

        item = frappe.get_doc({
            "doctype": "Item",
            "item_code": (
                f"GYM-PLAN-{frappe.generate_hash(length=8).upper()}"
            ),
            "item_name": self.plan_name,
            "item_group": item_group,
            "stock_uom": "Nos",
            "is_stock_item": 0,
            "is_sales_item": 1,
        })

        item.insert(ignore_permissions=True)
        self.item = item.name

    def on_update(self):
        self.sync_item_price()

    def sync_item_price(self):
        if not self.item or self.price is None:
            return

        price_list = get_selling_price_list()

        price_list_data = frappe.db.get_value(
            "Price List",
            price_list,
            ["currency", "selling", "enabled"],
            as_dict=True,
        )

        if (
            not price_list_data
            or not price_list_data.selling
            or not price_list_data.enabled
        ):
            frappe.throw(_("An enabled selling Price List is required."))

        item_price_name = frappe.db.get_value(
            "Item Price",
            {
                "item_code": self.item,
                "price_list": price_list,
                "selling": 1,
            },
            "name",
        )

        if item_price_name:
            item_price = frappe.get_doc(
                "Item Price", item_price_name
            )
            item_price.price_list_rate = self.price
            item_price.currency = price_list_data.currency
            item_price.save(ignore_permissions=True)
        else:
            item_price = frappe.get_doc({
                "doctype": "Item Price",
                "item_code": self.item,
                "price_list": price_list,
                "price_list_rate": self.price,
                "currency": price_list_data.currency,
                "selling": 1,
            })
            item_price.insert(ignore_permissions=True)
