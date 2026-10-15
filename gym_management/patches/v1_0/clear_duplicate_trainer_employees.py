"""Make Gym Trainer.employee ready to carry a unique index.

Runs under ``pre_model_sync`` because the unique constraint is added when the
DocType is synced, and MySQL refuses to build it while duplicates are present.
The oldest trainer keeps the employee; the rest are cleared and have to be
pointed at their own Employee record by hand.
"""

import frappe


def execute():
    if not frappe.db.has_column("Gym Trainer", "employee"):
        return

    duplicates = frappe.db.sql(
        """
        SELECT employee
        FROM `tabGym Trainer`
        WHERE IFNULL(employee, '') != ''
        GROUP BY employee
        HAVING COUNT(*) > 1
        """,
        pluck=True,
    )

    for employee in duplicates:
        names = frappe.get_all(
            "Gym Trainer",
            filters={"employee": employee},
            pluck="name",
            order_by="creation asc",
        )

        # Keep the first, release the employee from the others.
        for name in names[1:]:
            frappe.db.set_value("Gym Trainer", name, "employee", None, update_modified=False)
            frappe.log_error(
                f"Gym Trainer {name} shared Employee {employee}; the link was cleared "
                "so the employee field could be made unique.",
                "Gym trainer employee de-duplication",
            )
