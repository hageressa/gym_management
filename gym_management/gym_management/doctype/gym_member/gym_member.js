// Copyright (c) 2026, hager essa and contributors
// For license information, please see license.txt

frappe.ui.form.on("Gym Member", {
    refresh(frm) {
        // Standard address and contact block, the same one Customer uses.
        frappe.dynamic_link = { doc: frm.doc, fieldname: "name", doctype: "Gym Member" };
        if (frm.is_new()) {
            frappe.contacts.clear_address_and_contact(frm);
            return;
        }
        frappe.contacts.render_address_and_contact(frm);

        frm.add_custom_button(__("Create Membership"), function () {
            frappe.new_doc("Gym Membership", {
                member: frm.doc.name
            });
        }, __("Actions"));
    }
});
