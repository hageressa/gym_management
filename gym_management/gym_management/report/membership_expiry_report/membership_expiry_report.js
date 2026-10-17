frappe.query_reports["Membership Expiry Report"] = {
	filters: [
		{
			fieldname: "status",
			label: __("Membership Status"),
			fieldtype: "Select",
			options: "\nActive\nFrozen\nExpired\nCancelled",
			default: "Active",
		},
		{
			fieldname: "days",
			label: __("Expiring Within (Days)"),
			fieldtype: "Int",
			default: 30,
		},
		{
			fieldname: "from_date",
			label: __("Expiry From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("Expiry To Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "membership_plan",
			label: __("Membership Plan"),
			fieldtype: "Link",
			options: "Membership Plan",
		},
	],
};
