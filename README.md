# Gym Management System

A gym management application built with the Frappe Framework and ERPNext.
The application manages gym memberships, membership plans, class sessions,
class bookings, and member check-ins.

## Requirements

- Frappe Framework v15
- ERPNext v15
- A working Bench environment

## Installation

From your Frappe Bench directory, run:

```bash
bench get-app https://github.com/hageressa/gym_management.git --branch develop
bench --site gym.localhost install-app gym_management
```

Replace `gym.localhost` with your own site name if necessary.

If the app is already available in `apps/gym_management`, skip `bench get-app`.

## Main Features

- Membership plans with duration, price, and class-pack configuration.
- Gym membership status management, including active, frozen, expired,
  and cancelled states where supported by the membership workflow.
- Membership freeze history and freeze-status synchronization.
- Class sessions and class booking validation.
- Gym check-in records and related validation.
- Scheduled tasks for updating expired memberships, synchronizing freeze
  statuses, and sending membership-expiry reminders.

The exact features available depend on the DocTypes, permissions, and
workflows configured in the installed version.

## Scheduled Tasks

The app registers daily tasks for:

- Synchronizing membership freeze statuses.
- Updating expired memberships.
- Sending membership-expiry reminders when enabled in Gym Settings.

Scheduled execution depends on the site's scheduler being enabled and running.

## Running Tests

Run the full test suite for this app:

```bash
bench --site gym.localhost run-tests --app gym_management
```

Run the task tests only:

```bash
bench --site gym.localhost run-tests \
  --app gym_management \
  --module gym_management.test_tasks
```

Replace `gym.localhost` with your site name if necessary.

## Development

The app uses the Frappe Framework development workflow. After changing
DocTypes or their metadata, migrate or reload the relevant DocTypes as
appropriate for the change.

The repository uses pre-commit for code formatting and linting.

Install the hooks with:

```bash
cd apps/gym_management
pre-commit install
```

Configured tools include Ruff, ESLint, Prettier, and pyupgrade.

## Contributing

Contributions and bug reports are welcome. Please test changes before
submitting a pull request.

## License

MIT
