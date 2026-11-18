Configure the branch address on each sales journal through the **Address
Issued** field (`l10n_mx_address_issued_id`, from `l10n_mx_edi_extended`).

For foreign / generic customers (`XEXX010101000` / `XAXX010101000`):

- **Invoices** and **credit notes**: `LugarExpedicion` and
  `DomicilioFiscalReceptor` both take the branch ZIP of the journal.
- **Payment complements**:
  - If the reconciled invoices belong to a single branch, `LugarExpedicion` is
    set to that branch ZIP, matching the invoice `DomicilioFiscalReceptor`.
  - If the payment reconciles invoices from different branches, stamping is
    blocked with an explicit error (register one payment per branch).
  - If no journal defines a branch address, the standard behaviour (company ZIP)
    is kept.
