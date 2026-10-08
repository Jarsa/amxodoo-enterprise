This module adapts `l10n_mx_sat_purchase` to the Enterprise Mexican
localization (`l10n_mx_edi`).

When a purchase order is billed from a CFDI downloaded from the SAT:

- CFDIs whose fiscal folio is already registered in a vendor bill are not
  proposed.
- The status of the fiscal folio is validated against the SAT before the bill
  is created: cancelled or unknown CFDIs are rejected.
- The XML is imported by the standard CFDI importer, so the bill gets its
  `l10n_mx_edi.document` in the *Received* state with the fiscal folio and the
  SAT status already set.
