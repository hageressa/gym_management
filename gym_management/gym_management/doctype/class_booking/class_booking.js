frappe.ui.form.on("Class Booking", {
	setup(frm) {
		// Only sessions that are still scheduled and not in the past.
		frm.set_query("class_session", () => ({
			filters: {
				status: "Scheduled",
				session_date: [">=", frappe.datetime.get_today()],
			},
		}));
	},

	refresh(frm) {
		frm.trigger("show_seats_left");
	},

	class_session(frm) {
		frm.trigger("show_seats_left");
	},

	show_seats_left(frm) {
		if (!frm.doc.class_session) {
			frm.set_intro("");
			return;
		}

		frappe.db
			.get_value("Class Session", frm.doc.class_session, ["capacity", "booked_count"])
			.then(({ message }) => {
				if (!message) {
					return;
				}
				const left = Math.max((message.capacity || 0) - (message.booked_count || 0), 0);

				if (left > 0) {
					frm.set_intro(__("{0} seat(s) left in this session.", [left]), "green");
				} else {
					frm.set_intro(
						__("This session is full. New bookings go to the waitlist."),
						"orange"
					);
				}
			});
	},
});
