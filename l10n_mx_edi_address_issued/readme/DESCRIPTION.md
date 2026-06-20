In multi-branch environments the issued address (branch ZIP) is configured per
journal through the `l10n_mx_address_issued_id` field provided by
`l10n_mx_edi_extended`. For foreign or generic customers the SAT requires the
CFDI `DomicilioFiscalReceptor` to be equal to the `LugarExpedicion`
(validation **CFDI40149**); both must therefore be the branch ZIP.

This module guarantees that the branch issued address is used consistently
across the three CFDI flows for those customers:

- **Invoices** and **credit notes**: already handled by `l10n_mx_edi_extended`
  (which sets the issued address from the journal). This module depends on it
  and covers both flows with regression tests.
- **Payment complements** (Complemento de Pago): the standard flow keeps using
  the company (headquarters) ZIP as `LugarExpedicion`, so it no longer matches
  the invoice `DomicilioFiscalReceptor` and the PAC rejects the document:

      CFDI40149 - El campo DomicilioFiscalReceptor no es igual al valor del
      campo LugarExpedicion

  This module makes the payment `LugarExpedicion` follow the branch address of
  the reconciled invoice's journal, so both nodes match and the complement can
  be stamped.
