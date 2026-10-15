frappe.views.calendar["Class Session"] = {
	field_map: {
		start: "starts_on",
		end: "ends_on",
		id: "name",
		title: "subject",
		status: "status",
	},
	// Sessions store a date plus two times, so the server combines them into
	// the start/end datetimes the calendar expects.
	get_events_method: "gym_management.api.get_session_calendar_events",
	order_by: "session_date",
	gantt: false,
};
