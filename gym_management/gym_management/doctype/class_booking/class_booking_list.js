frappe.listview_settings["Class Booking"] = {
	add_fields: ["status", "waitlist_position"],

	get_indicator(doc) {
		const colours = {
			Booked: "green",
			Waitlisted: "orange",
			Attended: "blue",
			"No Show": "red",
			Cancelled: "grey",
		};

		// A waitlisted booking is only useful if you can see the queue position.
		const label =
			doc.status === "Waitlisted" && doc.waitlist_position
				? __("Waitlisted #{0}", [doc.waitlist_position])
				: __(doc.status);

		return [label, colours[doc.status] || "grey", "status,=," + doc.status];
	},
};
