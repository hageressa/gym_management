frappe.views.calendar["Class Session"] = {
    field_map: {
        start: "start_datetime",
        end: "end_datetime",
        id: "name",
        title: "gym_class",
    },
    order_by: "start_datetime",
    gantt: false,
};