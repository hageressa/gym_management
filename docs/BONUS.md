# Bonus features: design notes

Kept apart from `DECISIONS.md`, which the brief limits to two pages.

## Door-access integration

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

## Workout plans and body measurements

- **A measurement is its own document, not a child table on Gym Member.** Each
  visit is dated and has its own author (`measured_by`), the list view filters
  and sorts it by member and date, and adding a reading never rewrites the
  member record.
- **Exercises are a child table on Workout Plan.** An exercise only means
  something inside its plan, so it has no list of its own.
- **BMI is computed, not typed.** It follows from weight and height, so it is
  read-only and recalculated on every save, the same reasoning as Class
  Session `end_time`.
- **Empty optional measurements are 0, not refused.** Frappe stores an empty
  Float as 0, so only negative values are rejected; weight is the one required
  measurement and must be above zero.

## Personal training

- **Availability is its own DocType, not a table on Gym Trainer.** A trainer's
  windows change on their own schedule, and keeping them separate means
  editing availability never rewrites the trainer record, which links to an
  Employee.
- **Weekly windows, not dated slots.** A gym trainer's hours repeat by
  weekday. Leave and one-off changes would be the next step; they are not in
  scope.
- **A booking reuses the existing rules instead of copying them.** Membership
  validity comes from `get_valid_membership`; the time arithmetic uses
  `combine_date_time` and `format_time`; the overlap query has the same shape
  as Class Session's.
- **The trainer's group classes count as conflicts.** A trainer teaching a
  class cannot also be booked one to one.
- **Only Scheduled sessions are checked.** Marking a session Completed or
  Cancelled must save even if the membership has since expired.

## Member portal

- **The member is found by email, not by a new link field.** Gym Member
  already stores the email, so the login maps to the member without a schema
  change. If two members share an email the portal refuses rather than
  guessing whose bookings to show.
- **The member always comes from the session, never from the request.**
  `book_session(session)` takes no member argument, and `cancel_booking`
  checks that the booking belongs to the signed-in member. This is what makes
  `ignore_permissions` safe: Website Users hold no permission on Class Booking,
  and are not given any.
- **One booking path.** `book_class` was split so its body became
  `create_booking`; the Desk endpoint and the portal call the same function and
  differ only in who has been authorised. No booking rule lives in the portal.
- **A Frappe `www` page, not a Web Form.** A Web Form edits one document; this
  page lists sessions and acts on bookings, so a template with a small script
  calling whitelisted methods fits better.
