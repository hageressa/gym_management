frappe.ui.form.on("Gym Membership", {
    setup(frm) {
        // Gym Member has no "disabled" field; the real rule is that a
        // blacklisted member may not be sold a membership.
        frm.set_query("member", () => ({
            filters: { status: ["!=", "Blacklisted"] }
        }));
    },

    refresh(frm) {
        const status_colors = {
            Draft: "gray",
            Active: "green",
            Frozen: "orange",
            Expired: "red",
            Cancelled: "red"
        };

        if (frm.doc.status) {
            frm.set_indicator(
                __(frm.doc.status),
                status_colors[frm.doc.status] || "gray"
            );
        }

        if (frm.is_new() || frm.doc.docstatus !== 1) return;

        const status = frm.doc.status;
        const lock_fields = ["member", "membership_plan", "start_date", "auto_renew"];

        lock_fields.forEach(field => {
            frm.set_df_property(field, "read_only",
                ["Frozen", "Expired", "Cancelled"].includes(status) ? 1 : 0
            );
        });

        if (status === "Active" || status === "Frozen") {
            frm.add_custom_button(__("Freeze"), () => {
                frappe.prompt([
                    {
                        fieldname: "freeze_from",
                        label: __("Freeze From"),
                        fieldtype: "Date",
                        reqd: 1,
                        default: frappe.datetime.get_today()
                    },
                    {
                        fieldname: "freeze_to",
                        label: __("Freeze To"),
                        fieldtype: "Date",
                        reqd: 1
                    },
                    {
                        fieldname: "reason",
                        label: __("Reason"),
                        fieldtype: "Small Text"
                    }
                ], values => {
                    frappe.call({
                        method: "gym_management.api.freeze_membership",
                        args: {
                            membership_name: frm.doc.name,
                            freeze_from: values.freeze_from,
                            freeze_to: values.freeze_to,
                            reason: values.reason
                        },
                        freeze: true,
                        freeze_message: __("Saving freeze period..."),
                        callback: r => {
                            if (r.message) {
                                frappe.msgprint(
                                    r.message.message ||
                                    __("Freeze period saved.")
                                );
                                frm.reload_doc();
                            }
                        }
                    });
                }, __("Freeze Membership"), __("Save"));
            }, __("Actions"));
        }

        if (status === "Expired") {
            frm.add_custom_button(__("Renew"), () => {
                frappe.confirm(
                    __("Create a new membership for this member?"),
                    () => {
                        frappe.call({
                            method: "gym_management.api.renew_membership",
                            args: { membership_name: frm.doc.name },
                            freeze: true,
                            freeze_message: __("Renewing membership..."),
                            callback: r => {
                                if (r.message && r.message.name) {
                                    frappe.msgprint(
                                        __("New membership created: ") +
                                        r.message.name
                                    );
                                    frappe.set_route(
                                        "Form",
                                        "Gym Membership",
                                        r.message.name
                                    );
                                }
                            }
                        });
                    }
                );
            }, __("Actions"));
        }
    }
});
