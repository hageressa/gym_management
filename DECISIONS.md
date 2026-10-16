# Design Decisions — gym_management

## R1. ERPNext `Subscription` or custom renewal logic?

**Chose:** a custom `Gym Membership` submittable DocType, with ERPNext reused for everything financial.

`Subscription` exists to raise invoices on a repeating schedule. A gym membership is a
single fixed-term purchase that the front desk may pause mid-term, and pausing has to push
the end date out by the number of frozen days. `Subscription` has no concept of a paused
period: a freeze would mean editing `current_invoice_start` / `current_invoice_end` behind
its back, and its own scheduler would keep raising invoices for a member who is not
training. The states the business actually asks for — `Draft / Active / Frozen / Expired /
Cancelled` — do not map onto it either.

So the membership lifecycle is ours, and the money is ERPNext's:

| Concern | Where it lives |
|---|---|
| Billing identity | `Customer`, created on first save of a `Gym Member` |
| What was sold | A non-stock `Item` per `Membership Plan`, with `Item Price` kept in sync |
| The charge | A `Sales Invoice` created in `Gym Membership.on_submit` |
| Membership state, freezes, class balance | `Gym Membership` |

**Trade-off:** no automatic recurring billing. Renewal is explicit, through
`api.renew_membership`, which starts the new term the day after the old one ends. The
`subscription` link and `auto_renew` fields are on the DocType so a `Subscription` can be
attached later for members who want card-on-file billing, without reshaping the data model.

## R2. How trainers are modelled

**Chose:** a separate `Gym Trainer` DocType with an optional 1:1 link to `Employee`.

Custom fields on `Employee` were the alternative. They were rejected for two reasons. First,
`Employee` belongs to HR; a gym running this app without the HR module would still have to
carry it, and scheduling data would end up inside an HR master. Second, the fields a gym
needs — specialties, bio, whether the trainer is currently taking classes — are about the
timetable, not about employment.

`Gym Trainer` therefore holds `specialties` (a Table MultiSelect over a `Gym Specialty`
master, so the same specialty is spelled the same way everywhere), `bio` and `is_active`,
and links 1:1 to an `Employee`. The link is mandatory and unique, as the brief asks, and
`trainer_name` is fetched from the employee so the two can never drift apart. The seed
script creates an Employee per trainer for that reason.

**Trade-off:** two records per person. Accepted, because the alternative couples class
scheduling to payroll.

## R3. Pro-rated refunds on mid-term cancellation (design only)

Not implemented. The design:

1. **Value the unused part.** For `Days` / `Months` plans, `price × remaining_days /
   chargeable_days`, where `remaining_days` counts from the cancellation date to `end_date`
   and `chargeable_days` excludes days already spent frozen — a frozen day was not consumed,
   so the member should not be refunded for it twice. For a `Class Pack`,
   `price × classes_remaining / classes_included`.
2. **Issue a Credit Note, do not cancel the invoice.** A `Sales Invoice` with `is_return = 1`
   and `return_against` set to the original. Cancelling a submitted invoice erases revenue
   that was really earned for the period the member did train, and breaks the audit trail.
   Note that `Gym Membership.on_cancel` today *does* cancel the invoice — that path is for
   correcting a mistaken sale, not for a refund, and a refund flow would have to branch here.
3. **Pay it back** with a `Payment Entry` against the credit note.

**Needs a business answer before building:** whether a cancellation fee applies, whether
freeze days are refundable at all, and the tax treatment of a partial refund.

## R4. Two people booking the last spot

`ClassBooking.validate_capacity` takes a row lock on the session before it counts:

```python
frappe.db.get_value("Class Session", self.class_session, "name", for_update=True)
```

Frappe serves each request inside one transaction and commits at the end, so the second
request blocks on that row until the first has committed its booking, and then counts it.
The count is taken from `Class Booking` rows, not from the cached `booked_count` field —
`booked_count` is maintained by hooks for display and would be stale under a race.

**What is not proven.** There is no automated concurrency test. The unit tests mock the
database, so they exercise the ordering of the checks, not the locking. Proving this needs
two real parallel requests against a running site.

**What I would add next**, in order:

1. A test that opens two connections in separate threads, books the same last spot, and
   asserts exactly one `Booked` and one `Waitlisted` (or one failure).
2. A database-level backstop: a unique index on `(class_session, member)` for non-cancelled
   bookings. Duplicate booking is enforced in `validate_duplicate_booking` today, which is
   application-level only.
3. Load testing to confirm the lock does not serialise the whole booking endpoint under
   normal traffic.

## R5. Sources consulted

- [DocType controllers](https://docs.frappe.io/framework/user/en/basics/doctypes/controllers)
  and [the controller lifecycle](https://docs.frappe.io/framework-git/doctypes/controllers-lifecycle)
  — which hook fires when, and why the "one active membership" check belongs in
  `before_submit` rather than `on_submit`.
- [Hooks](https://docs.frappe.io/framework-git/server-side/hooks) — `doc_events`,
  `scheduler_events` and `fixtures` for the three roles.
- [Database API](https://docs.frappe.io/framework/user/en/api/database) — `db_set`,
  `db_insert` and `for_update`, which is how a submitted document is changed without
  calling `save()`.
- [Background jobs and the scheduler](https://docs.frappe.io/framework/user/en/api/background_jobs)
  — daily job registration and why the job must not call `frappe.db.commit()` itself.
- [Forum: using `for update` in Frappe queries](https://discuss.frappe.io/t/how-we-can-use-for-update-clause-in-frappe-get-all/55444)
  — confirmed `for_update=True` on `frappe.db.get_value` as the supported way to take the lock.
- `frappe/model/document.py` and `frappe/model/utils/rename_field.py` in
  [the Frappe source](https://github.com/frappe/frappe) — behaviour of `db_set` on submitted
  documents, and the rename used by the field-alignment patch.
- `erpnext/accounts/doctype/sales_invoice/sales_invoice.py` and
  `erpnext/accounts/doctype/subscription/subscription.py` in
  [the ERPNext source](https://github.com/frappe/erpnext) — the fields a Sales Invoice needs
  to submit, and what `Subscription` actually does on its schedule (R1).

## Bonus: door-access integration

The brief offers a `Webhook` **or** a REST integration for a door controller.
Both halves are here, and the split between them is the point:

- **Inbound is code.** `gym_management/door.py` exposes one guest endpoint the
  reader calls. It decides nothing of its own — it asks
  `get_membership_block_reason`, so the door and the front desk can never
  disagree about the same member. That is the payoff from having put that rule
  in one place earlier.
- **Outbound is configuration.** Frappe's built-in `Webhook` DocType posts every
  new `Gym Check In` to whatever system wants to hear about it. Writing a
  publisher by hand would have been duplicating the framework.

Guest access needed care, because the endpoint runs before any login:

| Risk | What stops it |
|---|---|
| Token recovered by timing the replies | `hmac.compare_digest` |
| Door left open while unconfigured | No token set raises, so it fails closed |
| Brute force | `@rate_limit(limit=60, seconds=60)` |
| Guest writing other records | `ignore_permissions` is used on that one insert and nowhere else; the Guest role holds no permission on any gym DocType |

**Not done:** the token is one shared secret, so a stolen reader means rotating
it on every door. A `Gym Door` record per reader, each with its own token and an
`is_active` flag, would contain that — it is the first thing to add if this ran
on more than one site.

## Deviations from the brief

None in the field definitions: `Class Session` stores `session_date` / `start_time` /
`end_time`, `Gym Class` exposes `default_trainer` / `default_room` / `default_capacity`, and
`Gym Room` and `Gym Trainer` use `is_active`, as specified. Two notes on how that was met:

- **The calendar view** needs a single start and end datetime, which the split fields do not
  provide directly. `api.get_session_calendar_events` combines the date and the two times
  server-side and the calendar config points at it, rather than storing a redundant datetime.
- **Existing data** is carried across by
  `gym_management/patches/v1_0/align_fields_with_task_spec.py`, which splits the old
  datetimes, converts the old `status` selects to `is_active`, and turns the old free-text
  `specialization` into linked `Gym Specialty` rows.

A `Gym Member` is named `MEM-####` rather than by a hash, and the member link field searches
`member_name`, `phone` and `email`, so the front desk can find somebody by what they know.
