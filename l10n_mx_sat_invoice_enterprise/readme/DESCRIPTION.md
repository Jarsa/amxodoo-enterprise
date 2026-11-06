This module adapts `l10n_mx_sat_invoice` to the Enterprise Mexican
localization (`l10n_mx_edi`).

When an invoice is created from a CFDI downloaded from the SAT:

- CFDIs whose fiscal folio is already registered in an invoice are rejected,
  and the status of the fiscal folio is validated against the SAT: cancelled
  or unknown CFDIs are rejected and the SAT document is updated.
- The invoice gets its `l10n_mx_edi.document` in the *Sent* state (issued
  CFDIs, so Odoo does not stamp them again) or *Received* state (received
  CFDIs) with the XML, the fiscal folio and the SAT status.
- The payment way, payment policy, usage and related CFDIs (origin) of the
  invoice are taken from the CFDI.
