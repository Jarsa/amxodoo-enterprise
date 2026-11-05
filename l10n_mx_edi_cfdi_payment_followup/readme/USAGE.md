## Payment states

Every payment shows a **CFDI Payment State**:

- **Not Required** — no complement is expected (non-PPD, before the start date,
  not a vendor payment, or manually ignored).
- **Pending** — a PPD vendor bill is reconciled and the complement has not been
  requested yet.
- **Requested** — the request email was sent and the XML is awaited.
- **Received** — one or more valid complements were received, but they do not
  cover the whole payment yet (another complement is expected).
- **Validated** — the valid CFDI payment complement XML(s) received cover the
  payment and their `l10n_mx_edi.document` were created.
- **Error** — a received XML failed validation; a follow-up activity is raised.

Whether a vendor bill is **PPD** is read from the `MetodoPago` of its own CFDI
(the XML received from the vendor), which is the source of truth. Only when the
bill has no CFDI attached the *Payment Policy* field of the bill is used
instead.

## Requesting the complement

1.  Open a vendor payment (or a bank reconciliation line) in *Pending*,
    *Requested* or *Error* state.
2.  (Optional) Upload the bank transfer voucher in the **Payment Receipt**
    field (available in both the payment form and the bank reconciliation view)
    so it is attached to the email.
3.  Press **Request Complement** (or **Request Complements** for batch processing
    from the bank reconciliation header). An email is sent to the vendor contact, in
    the partner's language, listing each related invoice with its currency and vendor
    reference and the partial amount applied; the state moves to *Requested*.

The button is only visible for **vendor** payments (those reconciled against a
vendor bill or refund); it is hidden for customer collections.

## Receiving and validating the XML

Attach the CFDI payment-complement XML in the payment chatter (or directly on
the payment). Only payments in scope are processed (see *Payment states*); an
XML attached to an invoice or to a payment that does not need a complement is
kept as a plain file. The module parses it automatically and validates:

1.  The document is a payment complement (`TipoDeComprobante = "P"`).
2.  The Fiscal Stamp (UUID) is present.
3.  `FormaDePagoP` is SPEI (`"03"`).
4.  `FechaPago` has a valid format.
5.  `FechaPago` is not before the payment date and not after it by more than
    the configured tolerance.
6.  Each `DoctoRelacionado/IdDocumento` matches a reconciled invoice UUID
    (case-insensitive).
7.  The sum of `Monto` of all the complements received for the payment does
    not exceed the Odoo payment amount (±1.00).

The outstanding balance (`ImpSaldoInsoluto`) is not checked, so a complement
for one installment of a PPD invoice is valid.

When the complements cover the payment the state becomes *Validated* and prior
error activities are closed. When they cover only part of it (e.g. CFE issues
two complements for a single transfer) the state becomes *Received* and the
missing amount is logged in the chatter; attach the remaining complement(s) to
complete it. On failure the state becomes *Error* and an activity is raised for
the responsible team. A **replacement** XML (different UUID that covers the
payment by itself) is accepted and logged in the chatter for review.

If the XML of a received complement is emptied (e.g. by a server action that
clears the attachment), it no longer counts: the payment goes back to
*Received* or *Pending* and the XML can be attached again.

## Ignoring a payment

When a payment should not be followed up (e.g. a complement will never arrive),
select it in the payments list or in the bank reconciliation list and press
**CFDI Not Required** (also available as *Action ⚙️ / Mark as CFDI Not
Required*) to set it to *Not Required*; the choice persists across
recomputations. Press **Resume CFDI Follow-up** to put it back in scope. A
received and valid XML always overrides the ignore and validates the complement
anyway.
