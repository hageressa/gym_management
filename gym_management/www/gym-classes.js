frappe.ready(() => {
	document.querySelectorAll("[data-gym-action]").forEach((button) => {
		button.addEventListener("click", () => run_action(button));
	});
});

function run_action(button) {
	const is_booking = button.dataset.gymAction === "book";
	if (!is_booking && !window.confirm(__("Cancel this booking?"))) {
		return;
	}

	button.disabled = true;
	frappe.call({
		method: is_booking
			? "gym_management.portal.book_session"
			: "gym_management.portal.cancel_booking",
		args: is_booking ? { session: button.dataset.session } : { booking: button.dataset.booking },
		callback: (r) => {
			// Leave time to read a server notice, such as a late-cancellation warning.
			setTimeout(() => window.location.reload(), r._server_messages ? 2500 : 0);
		},
		always: () => {
			button.disabled = false;
		},
	});
}
