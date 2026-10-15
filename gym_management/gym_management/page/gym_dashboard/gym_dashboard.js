frappe.pages["gym-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Gym Dashboard"),
		single_column: true,
	});

	const dashboard = new GymDashboard(page);
	page.set_primary_action(__("Refresh"), () => dashboard.load(), "refresh");
	dashboard.load();
};

class GymDashboard {
	constructor(page) {
		this.page = page;
		this.body = $('<div class="gym-dashboard">').appendTo(page.main);
	}

	load() {
		this.body.html(`<p class="text-muted">${__("Loading…")}</p>`);

		// One call for every number on the page: the server does the counting.
		frappe.call({
			method: "gym_management.api.get_dashboard_data",
			callback: ({ message }) => {
				if (!message) {
					this.body.html(`<p class="text-muted">${__("No data available.")}</p>`);
					return;
				}
				this.render(message);
			},
		});
	}

	render(data) {
		this.body.empty();
		this.render_cards(data);
		this.render_sessions(data.today_sessions || []);
	}

	render_cards(data) {
		const sessions_today = (data.today_sessions || []).length;

		const cards = [
			{
				label: __("Active Members"),
				value: data.active_members,
				route: ["List", "Gym Membership", { status: "Active", docstatus: 1 }],
			},
			{
				label: __("Expiring in 7 Days"),
				value: data.expiring_soon,
				// Only worth drawing the eye when there is something to act on.
				warn: data.expiring_soon > 0,
				route: ["List", "Gym Membership", { status: "Active" }],
			},
			{
				label: __("Sessions Today"),
				value: sessions_today,
				route: ["List", "Class Session"],
			},
			{
				label: __("Revenue This Month"),
				value: format_currency(data.revenue_this_month || 0, data.currency),
			},
		];

		const row = $('<div class="row">').appendTo(this.body);

		cards.forEach((card) => {
			const column = $('<div class="col-sm-3 col-xs-6">').appendTo(row);

			const $card = $(`
				<div class="card" style="padding: 14px; margin-bottom: 15px; height: 100%;
					cursor: ${card.route ? "pointer" : "default"}">
					<div class="text-muted ellipsis" style="font-size: 12px; margin-bottom: 6px">
						${frappe.utils.escape_html(card.label)}
					</div>
					<div class="ellipsis" style="font-size: 20px; font-weight: 600; line-height: 1.3;
						color: ${card.warn ? "var(--orange-600, #b45309)" : "inherit"}">
						${frappe.utils.escape_html(String(card.value))}
					</div>
				</div>
			`).appendTo(column);

			if (card.route) {
				$card.on("click", () => frappe.set_route(...card.route));
			}
		});
	}

	render_sessions(sessions) {
		const section = $(`
			<div style="margin-top: 20px">
				<h5>${__("Today's Sessions")}</h5>
			</div>
		`).appendTo(this.body);

		if (!sessions.length) {
			$(`<p class="text-muted">${__("No sessions scheduled for today.")}</p>`).appendTo(section);
			return;
		}

		const table = $(`
			<table class="table table-bordered">
				<thead>
					<tr>
						<th style="width: 15%">${__("Time")}</th>
						<th>${__("Class")}</th>
						<th>${__("Trainer")}</th>
						<th style="width: 12%">${__("Booked")}</th>
						<th style="width: 30%">${__("Fill Rate")}</th>
					</tr>
				</thead>
				<tbody></tbody>
			</table>
		`).appendTo(section);

		const tbody = table.find("tbody");

		sessions.forEach((session) => {
			const fill = session.fill_rate || 0;
			const colour = fill >= 100 ? "red" : fill >= 70 ? "orange" : "green";

			const row = $(`
				<tr style="cursor: pointer">
					<td>${frappe.datetime.str_to_user(session.start_datetime)}</td>
					<td>${frappe.utils.escape_html(session.class_name || session.gym_class || "")}</td>
					<td>${frappe.utils.escape_html(session.trainer_name || session.trainer || "")}</td>
					<td>${session.booked_count || 0} / ${session.capacity || 0}</td>
					<td>
						<div class="progress" style="margin: 0; height: 8px">
							<div class="progress-bar background-${colour}"
								style="width: ${Math.min(fill, 100)}%"></div>
						</div>
						<span class="text-muted" style="font-size: 11px">${fill}%</span>
					</td>
				</tr>
			`).appendTo(tbody);

			row.on("click", () => frappe.set_route("Form", "Class Session", session.name));
		});
	}
}