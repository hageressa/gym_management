// Copyright (c) 2026, hager essa and contributors
// For license information, please see license.txt

frappe.ui.form.on("Gym Member", {
    refresh(frm) {
        if (frm.is_new() || !frm.doc.name) return;

        frm.add_custom_button(__("Create Membership"), function () {
            frappe.new_doc("Gym Membership", {
                member: frm.doc.name
            });
        }, __("Actions"));
    }
});
