# Gym Management System — Design Decisions

## R1. Custom Membership vs ERPNext Subscription

The current implementation uses a custom Gym Membership DocType linked to ERPNext Customer, Item, and Sales Invoice records. This keeps gym-specific states such as Frozen, Expired, and Cancelled, class entitlements, and freeze history in one place while reusing ERPNext invoicing.

ERPNext Subscription is a stronger option when automated recurring billing, billing intervals, and subscription lifecycle management are central requirements. It introduces additional configuration and synchronization between the subscription and gym-specific membership state. For this assessment, the custom membership is the simpler fit. The existing subscription link can support a future integration if recurring billing becomes a requirement.

## R2. Trainer Data Model

Gym Trainer links to the standard ERPNext Employee DocType rather than duplicating employee identity and HR information. Gym-specific details, such as specialties and trainer availability, belong in Gym Trainer. This reuses employee records and avoids maintaining two sources of truth for the same person.

## R3. Pro-rated Refunds

A cancellation refund should be calculated from the unused membership period or unused class entitlement, according to a documented gym policy. The system should create a credit note against the original Sales Invoice, using ERPNext accounting workflows, rather than deleting or editing submitted accounting records. The refund policy, taxes, and approval rules must be confirmed with the business before implementation.

## R4. Concurrency and the Last Available Spot

Checking capacity before inserting a booking is not sufficient when two requests arrive simultaneously. The current implementation acquires a row lock for the Class Session before checking capacity. This is a first step toward serialization, but the complete transaction behavior and freshness of the booking count still require dedicated concurrent-request tests before claiming that last-slot races are prevented. The booking must be inserted in the same transaction. If capacity is exhausted, the request should enter the waitlist only when waitlisting is enabled; otherwise it should fail with a clear message.

## R5. References and Verification

Implementation decisions should be checked against the official Frappe Framework and ERPNext documentation, the installed application source, and relevant Frappe forum discussions.

- Frappe Framework documentation: https://docs.frappe.io/framework
- ERPNext documentation: https://docs.frappe.io/erpnext
- Frappe Framework source: https://github.com/frappe/frappe
- ERPNext source: https://github.com/frappe/erpnext

Before delivery, verify each decision against the final code and record any additional sources actually consulted. This document describes design rationale; it does not claim that unimplemented features, such as pro-rated refunds or transaction-safe capacity locking, are already available.
