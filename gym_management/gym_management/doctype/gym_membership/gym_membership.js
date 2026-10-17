frappe.ui.form.on("Gym Membership", {
	setup(frm) {
		// Gym Member has no "disabled" field; the real rule is that a
		// blacklisted member may not be sold a membership.
		frm.set_query("member", () => ({
			filters: { status: ["!=", "Blacklisted"] },
		}));
		frm.set_query("membership_plan", () => ({ filters: { is_active: 1 } }));
	},

	refresh(frm) {
		frm.trigger("show_status_indicator");
		frm.trigger("lock_fields_once_settled");
		frm.trigger("add_action_buttons");
	},

	show_status_indicator(frm) {
		const colours = {
			Draft: "grey",
			Active: "green",
			Frozen: "orange",
			Expired: "red",
			Cancelled: "grey",
		};

		if (frm.doc.status) {
			frm.page.set_indicator(__(frm.doc.status), colours[frm.doc.status] || "grey");
		}
	},

	lock_fields_once_settled(frm) {
		if (frm.is_new() || frm.doc.docstatus !== 1) {
			return;
		}

		// Once a membership is frozen, expired or cancelled, its terms are history.
		const settled = ["Frozen", "Expired", "Cancelled"].includes(frm.doc.status);

		["member", "membership_plan", "start_date", "auto_renew"].forEach((field) => {
			frm.set_df_property(field, "read_only", settled ? 1 : 0);
		});
	},

	add_action_buttons(frm) {
		if (frm.is_new() || frm.doc.docstatus !== 1) {
			return;
		}

		if (frm.doc.sales_invoice && frm.doc.status !== "Cancelled") {
			frm.add_custom_button(__("Record Payment"), () => record_payment(frm), __("Actions"));
		}

		if (["Active", "Frozen"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Freeze"), () => freeze_membership(frm), __("Actions"));
		}

		if (frm.doc.status === "Expired") {
			frm.add_custom_button(__("Renew"), () => renew_membership(frm), __("Actions"));
		}
	},
});

function freeze_membership(frm) {
	frappe.prompt(
		[
			{
				fieldname: "freeze_from",
				label: __("Freeze From"),
				fieldtype: "Date",
				reqd: 1,
				default: frappe.datetime.get_today(),
			},
			{
				fieldname: "freeze_to",
				label: __("Freeze To"),
				fieldtype: "Date",
				reqd: 1,
			},
			{
				fieldname: "reason",
				label: __("Reason"),
				fieldtype: "Small Text",
			},
		],
		(values) => {
			frappe.call({
				method: "gym_management.api.freeze_membership",
				args: {
					membership_name: frm.doc.name,
					freeze_from: values.freeze_from,
					freeze_to: values.freeze_to,
					reason: values.reason,
				},
				freeze: true,
				freeze_message: __("Saving freeze period…"),
				callback: ({ message }) => {
					if (!message) {
						return;
					}
					frappe.show_alert(
						{
							message: __("Frozen. Membership now ends {0}.", [
								frappe.datetime.str_to_user(message.end_date),
							]),
							indicator: "orange",
						},
						7
					);
					frm.reload_doc();
				},
			});
		},
		__("Freeze Membership"),
		__("Freeze")
	);
}

function renew_membership(frm) {
	frappe.confirm(__("Create and submit a new membership for this member?"), () => {
		frappe.call({
			method: "gym_management.api.renew_membership",
			args: { membership_name: frm.doc.name },
			freeze: true,
			freeze_message: __("Renewing membership…"),
			callback: ({ message }) => {
				if (message && message.name) {
					frappe.set_route("Form", "Gym Membership", message.name);
				}
			},
		});
	});
}

function record_payment(frm) {
	// ERPNext builds the Payment Entry from the invoice, with the outstanding amount filled in.
	frappe.call({
		method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry",
		args: { dt: "Sales Invoice", dn: frm.doc.sales_invoice },
		callback: (r) => {
			const doc = frappe.model.sync(r.message)[0];
			frappe.set_route("Form", doc.doctype, doc.name);
		},
	});
}
