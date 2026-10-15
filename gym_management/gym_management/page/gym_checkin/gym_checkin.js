frappe.pages["gym-checkin"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Front Desk Check In"),
		single_column: true,
	});

	new FrontDeskCheckIn(page);
};

// How long to wait after the last keystroke before asking the server.
const SEARCH_DELAY_MS = 300;

class FrontDeskCheckIn {
	constructor(page) {
		this.page = page;
		this.search_timer = null;
		this.build();
	}

	build() {
		this.body = $(`
			<div style="max-width: 640px">
				<input type="text" class="form-control member-search" autocomplete="off"
					placeholder="${__("Search by name, phone, email or scan a member card")}"
					style="font-size: 16px; padding: 10px">
				<div class="search-results" style="margin-top: 10px"></div>
				<div class="member-panel" style="margin-top: 15px"></div>
			</div>
		`).appendTo(this.page.main);

		this.input = this.body.find(".member-search");
		this.results = this.body.find(".search-results");
		this.panel = this.body.find(".member-panel");

		this.input.on("input", () => this.queue_search());
		this.input.focus();
	}

	queue_search() {
		// Debounced so a scanner or fast typist does not fire a call per character.
		clearTimeout(this.search_timer);
		this.search_timer = setTimeout(() => this.search(), SEARCH_DELAY_MS);
	}

	search() {
		const text = this.input.val().trim();
		this.panel.empty();

		if (text.length < 2) {
			this.results.empty();
			return;
		}

		frappe.call({
			method: "gym_management.api.find_members",
			args: { search_text: text },
			callback: ({ message }) => this.render_results(message || []),
		});
	}

	render_results(members) {
		this.results.empty();

		if (!members.length) {
			this.results.html(`<p class="text-muted">${__("No member found.")}</p>`);
			return;
		}

		// A single exact hit (a scanned card) goes straight through.
		if (members.length === 1) {
			this.select_member(members[0]);
			return;
		}

		const list = $('<div class="list-group">').appendTo(this.results);

		members.forEach((member) => {
			$(`
				<a class="list-group-item" href="#" style="display: block; padding: 10px">
					<strong>${frappe.utils.escape_html(member.member_name || member.name)}</strong>
					<span class="text-muted" style="margin-left: 8px">
						${frappe.utils.escape_html(member.phone || "")}
					</span>
				</a>
			`)
				.appendTo(list)
				.on("click", (event) => {
					event.preventDefault();
					this.select_member(member);
				});
		});
	}

	select_member(member) {
		this.current_member = member;
		this.results.empty();
		this.panel.html(`<p class="text-muted">${__("Checking membership…")}</p>`);

		frappe.call({
			method: "gym_management.api.get_check_in_status",
			args: { member: member.name },
			callback: ({ message }) => this.render_panel(message),
		});
	}

	render_panel(status) {
		if (!status) {
			this.panel.empty();
			return;
		}

		const member = this.current_member;
		const allowed = Boolean(status.allowed);
		const background = allowed ? "#d4edda" : "#f8d7da";
		const text_colour = allowed ? "#155724" : "#721c24";
		const headline = allowed ? __("ALLOWED") : __("ENTRY DENIED");

		this.panel.empty();

		const card = $(`
			<div class="card" style="padding: 0; overflow: hidden">
				<div style="background: ${background}; color: ${text_colour}; padding: 18px">
					<div style="font-size: 24px; font-weight: 700">${headline}</div>
					<div style="font-size: 15px; margin-top: 4px">
						${frappe.utils.escape_html(member.member_name || member.name)}
					</div>
					${
						status.reason
							? `<div style="margin-top: 6px">${frappe.utils.escape_html(status.reason)}</div>`
							: ""
					}
				</div>
				<div class="details" style="padding: 14px"></div>
			</div>
		`).appendTo(this.panel);

		this.render_details(card.find(".details"), status, allowed);
	}

	render_details(container, status, allowed) {
		const rows = [
			[__("Membership"), status.membership],
			[__("Plan"), status.plan],
			[__("Status"), status.status],
			[__("Valid until"), status.end_date ? frappe.datetime.str_to_user(status.end_date) : null],
			[__("Classes left"), status.classes_remaining || null],
		].filter(([, value]) => value);

		rows.forEach(([label, value]) => {
			$(`
				<div style="display: flex; justify-content: space-between; padding: 3px 0">
					<span class="text-muted">${label}</span>
					<span>${frappe.utils.escape_html(String(value))}</span>
				</div>
			`).appendTo(container);
		});

		if (!allowed) {
			return;
		}

		$(`<button class="btn btn-primary btn-block" style="margin-top: 12px">${__("Check In")}</button>`)
			.appendTo(container)
			.on("click", (event) => this.check_in($(event.currentTarget)));
	}

	check_in($button) {
		$button.prop("disabled", true).text(__("Checking in…"));

		frappe.call({
			method: "gym_management.api.check_in_member",
			args: { member: this.current_member.name },
			callback: ({ message }) => {
				if (!message) {
					$button.prop("disabled", false).text(__("Check In"));
					return;
				}
				frappe.show_alert(
					{ message: __("Checked in: {0}", [message.name]), indicator: "green" },
					5
				);
				this.reset();
			},
			error: () => {
				// The controller refused it; show the member's current state again.
				$button.prop("disabled", false).text(__("Check In"));
				this.select_member(this.current_member);
			},
		});
	}

	reset() {
		this.current_member = null;
		this.panel.empty();
		this.results.empty();
		this.input.val("").focus();
	}
}
