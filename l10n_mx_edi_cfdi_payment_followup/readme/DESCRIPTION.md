This module automates the tracking, request, validation and operational
control of **CFDI Payment Complements** (*Complementos de Pago*, CFDI 4.0 /
Pagos 2.0) for Mexican **PPD** invoices.

For **vendor payments** it lets you request the complement from the supplier,
receive the XML, validate it against the Odoo data and follow up automatically
until it is received. For **customer collections** it detects which payments
require a complement and surfaces the state on every linked record.

Each payment (the `account.move` of type *entry* behind an `account.payment`
or an `account.bank.statement.line`) gets a **CFDI Payment State** that moves
through `Not Required → Pending → Requested → Validated`, with an `Error`
branch when a received XML fails validation.

Main features:

- **CFDI Payment State** field, stored and color-coded on payments, the list
  view and the bank reconciliation widget, with search filters and grouping.
- **Request Complement** email to the vendor, including the related invoices
  with the vendor reference (folio) and the **partial amount actually applied**
  to each invoice, plus an optional **bank transfer receipt** (PDF) attached
  from a dedicated field. The email is rendered in the partner's language.
- **Automatic XML processing**: any CFDI payment-complement XML posted in the
  chatter (or attached to the payment) is parsed and validated against 8 rules
  (payment form, dates, reconciled UUIDs, outstanding balance, amount…). On
  success an `l10n_mx_edi.document` is created and the state becomes
  *Validated*; on failure the state becomes *Error* and a follow-up activity is
  raised.
- The **Request Complement** button is shown only for vendor payments
  (reconciled against a vendor bill/refund); it is hidden for customer
  collections.
- **Ignore / Revert** server actions to mark a payment as *Not Required*
  (reversibly) when no complement is expected, available both on payments and
  bank statement lines. A received and valid XML still overrides the ignore.
- A dedicated **activity type** assigned to a configurable **responsible team**
  (via OCA `mail_activity_team`), so error and replacement activities are
  picked up by the team members.
- **Scheduled action** that re-sends reminders for overdue *Requested*
  payments, and a per-company **start date** so installing on a database with
  years of history stays fast.
