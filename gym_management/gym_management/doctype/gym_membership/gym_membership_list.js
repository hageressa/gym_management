frappe.listview_settings["Gym Membership"] = {
	add_fields: ["status"],

	get_indicator(doc) {
		const colours = {
			Draft: "grey",
			Active: "green",
			Frozen: "orange",
			Expired: "red",
			Cancelled: "grey",
		};

		return [__(doc.status), colours[doc.status] || "grey", "status,=," + doc.status];
	},
};
