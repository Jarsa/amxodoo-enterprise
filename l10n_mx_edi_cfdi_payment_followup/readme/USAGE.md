## Payment states

Every payment shows a **CFDI Payment State**:

- **Not Required** — no complement is expected (non-PPD, before the start date,
  not a vendor payment, or manually ignored).
- **Pending** — a PPD vendor bill is reconciled and the complement has not been
  requested yet.
- **Requested** — the request email was sent and the XML is awaited.
- **Validated** — a valid CFDI payment complement XML was received and the
  `l10n_mx_edi.document` was created.
- **Error** — a received XML failed validation; a follow-up activity is raised.

## Requesting the complement

1.  Open a vendor payment (or a bank reconciliation line) in *Pending*,
    *Requested* or *Error* state.
2.  (Optional) Upload the bank transfer voucher in the **Payment Receipt**
    field so it is attached to the email.
3.  Press **Request Complement**. An email is sent to the vendor contact, in
    the partner's language, listing each related invoice with its vendor
    reference and the partial amount applied; the state moves to *Requested*.
    From the bank reconciliation list you can use **Send CFDI Reminders** to do
    this in batch.

The button is only visible for **vendor** payments (those reconciled against a
vendor bill or refund); it is hidden for customer collections.

## Receiving and validating the XML

Attach the CFDI payment-complement XML in the payment chatter (or directly on
the payment). The module parses it automatically and validates:

1.  The document is a payment complement (`TipoDeComprobante = "P"`).
2.  The Fiscal Stamp (UUID) is present.
3.  `FormaDePagoP` is SPEI (`"03"`).
4.  `FechaPago` has a valid format.
5.  `FechaPago` is not before the payment date and not after it by more than
    the configured tolerance.
6.  Each `DoctoRelacionado/IdDocumento` matches a reconciled invoice UUID.
7.  `ImporteSaldoInsoluto` is `"0.00"`.
8.  The sum of `Monto` matches the Odoo payment amount (±1.00).

On success the state becomes *Validated* and prior error activities are closed.
On failure the state becomes *Error* and an activity is raised for the
responsible team. A **replacement** XML (different UUID) is accepted and logged
in the chatter for review.

## Ignoring a payment

When a payment should not be followed up (e.g. a complement will never arrive),
select it and use *Action ⚙️ / Ignore CFDI Complement* to set it to *Not
Required*; the choice persists across recomputations. Use *Action ⚙️ / Revert
CFDI Complement Ignore* to resume the follow-up. These actions are available on
both payments and bank statement lines. A received and valid XML always
overrides the ignore and validates the complement anyway.
