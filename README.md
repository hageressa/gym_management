# gym_management

A Frappe app that runs a gym on top of a standard ERPNext site: members, membership plans,
a class timetable, bookings with a waitlist, front-desk check-in, and freezes — with the
billing handled by ERPNext's own Customer, Item and Sales Invoice records rather than
reimplemented.

- Frappe v15, ERPNext v15, Python 3.10+

## Install

From your bench directory:

```bash
# 1. the app
bench get-app https://github.com/hageressa/gym_management.git --branch develop

# 2. a site with ERPNext on it
bench new-site gym.localhost --install-app erpnext

# 3. this app
bench --site gym.localhost install-app gym_management
bench --site gym.localhost migrate
```

Open `http://gym.localhost:8000` and finish the ERPNext setup wizard. **A company must
exist with a default receivable account, income account and cost center**, otherwise
submitting a membership cannot raise its Sales Invoice and will tell you which setting is
missing.

Then load the sample data:

```bash
bench --site gym.localhost execute gym_management.seed.run
```

That creates an item group, three plans, two trainers with specialties, two rooms, two
classes and three members, plus upcoming sessions. It is safe to run again — every record is
looked up before it is created. One class ("HIIT Express") has a capacity of 2 so the
waitlist is easy to demonstrate.

## Try it

| What | Where |
|---|---|
| Manager dashboard | `/app/gym-dashboard` |
| Front-desk check-in | `/app/gym-checkin` |
| Timetable as a calendar | Class Session list → Calendar view |

A full pass: open a **Gym Member** → create a **Gym Membership** on a plan → **Submit** it
(a Sales Invoice is created and the status becomes Active) → book that member onto a
**Class Session** → check them in from the front-desk page. Use **Actions → Freeze** on the
membership to pause it, then try the check-in again to see it refused.

## Screenshots

| | |
|---|---|
| Membership purchased, invoice raised | `docs/screenshots/01-membership-purchase.png` |
| Third booking on a session of two goes to the waitlist | `docs/screenshots/02-class-booking-waitlist.png` |
| Check-in refused for a frozen membership | `docs/screenshots/03-check-in-blocked.png` |
| Manager dashboard | `docs/screenshots/04-dashboard.png` |
| Timetable as a calendar | `docs/screenshots/05-session-calendar.png` |
| A freeze extending the end date | `docs/screenshots/06-membership-frozen.png` |

## Roles

Shipped as fixtures, so they exist after install:

- **Gym Manager** — everything, including submitting and cancelling memberships.
- **Front Desk** — members, memberships, bookings and check-ins.
- **Trainer** — reads the timetable and marks attendance on bookings.

## Scheduled jobs

Registered as daily tasks in `hooks.py`:

- `tasks.sync_freeze_statuses` — moves memberships between Active and Frozen as freeze
  periods start and end.
- `tasks.update_expired_memberships` — marks memberships Expired past their end date.
- `tasks.send_membership_expiry_reminders` — emails members whose membership expires within
  `Gym Settings.expiry_reminder_days`, once each.

These need the site scheduler to be running (`bench --site gym.localhost enable-scheduler`).
To check one by hand:

```bash
bench --site gym.localhost execute gym_management.tasks.update_expired_memberships
```

## Whitelisted API

In `gym_management/api.py`:

| Method | Does |
|---|---|
| `book_class(session, member)` | Books a member; the controller decides Booked vs Waitlisted |
| `get_available_sessions(date_from, date_to)` | Scheduled sessions in a range that still have room |
| `freeze_membership(membership_name, freeze_from, freeze_to, reason)` | Adds a freeze period and pushes the end date out |
| `renew_membership(membership_name)` | Submits a replacement membership for an expired one |
| `get_dashboard_data()` | Every figure on the dashboard, in one call |
| `find_members(search_text)` | Front-desk lookup by name, phone, email or id |
| `get_check_in_status(member)` | Whether the member may enter today, and why not |
| `check_in_member(member, method)` | Records the check-in |

## Door access (bonus)

A card reader at the entrance is not a Frappe user, so it authenticates with a
shared token rather than a login.

1. Put a secret in **Gym Settings → Door Access Token**.
2. Point the reader at the endpoint:

```bash
curl -X POST http://gym.localhost:8000/api/method/gym_management.door.door_access \
  -H "Content-Type: application/json" \
  -d '{"member": "MEM-0003", "token": "<your token>"}'
```

It answers `{"open": true, "check_in": "CHECKIN-0007", ...}` or
`{"open": false, "reason": "membership is frozen today", ...}` — the same
decision the front desk gets, because both ask `get_membership_block_reason`.
A successful call records a `Gym Check In` with `method = "Card"`.

The endpoint is guest-accessible, so it is guarded: the token is compared with
`hmac.compare_digest`, an unset token fails closed, rejected attempts are
logged, and the method is rate limited to 60 calls a minute.

**Telling another system about an entry** needs no code. Create a stock Frappe
**Webhook** with DocType `Gym Check In`, event `after_insert`, your controller's
URL, and the fields you want in the body (`member`, `membership`,
`check_in_time`, `method`).

## Tests

```bash
bench --site gym.localhost run-tests --app gym_management
```

88 tests. A single module:

```bash
bench --site gym.localhost run-tests \
  --module gym_management.gym_management.doctype.class_booking.test_class_booking
```

Most are unit tests with the database mocked, so they are fast and do not need seed data.
`test_freeze_integration.py` is the exception: it creates a real plan, member and submitted
membership and freezes it, to prove the freeze writes correctly to a document that is
already submitted.

If `run-tests` refuses to start, the site needs developer mode:

```bash
bench --site gym.localhost set-config developer_mode 1
bench --site gym.localhost set-config allow_tests true
```

## Assumptions

- **One active membership per member**, enforced in `before_submit`. Renewal starts the day
  after the old term ends.
- **A session runs inside one day.** Overlap checks compare times within the same
  `session_date`, which is why a session cannot cross midnight.
- **A frozen membership blocks entry**, as the brief asks. The daily job flips the status
  back to Active when the freeze ends; check-in also reads the freeze dates directly, so a
  member is never refused on a stale status.
- **A class pack is charged when the class is booked**, not when it is attended, and the
  class is returned if the booking is cancelled. Charging on attendance would let a member
  book more classes than they had paid for.
- **Invoices are not created twice.** `on_submit` returns early if a Sales Invoice is
  already linked, so retrying a failed submit cannot double-charge.
- The **currency, price list and company** come from the site's own defaults rather than
  being hard-coded, so the app works on a site set up for any country.

## Development

```bash
cd apps/gym_management
pre-commit install
```

Ruff, ESLint, Prettier and pyupgrade run on commit. Settings are in `pyproject.toml` and
`.pre-commit-config.yaml`.

Design decisions and the research answers are in [DECISIONS.md](DECISIONS.md).

## Licence

MIT
