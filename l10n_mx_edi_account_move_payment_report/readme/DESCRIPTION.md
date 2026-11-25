This module completes the CFDI payment receipt that `l10n_mx_edi` prints
for payments and bank transactions:

- The payment receipt shows the company VAT next to the VAT of the CFDI
  when they differ, and the fiscal regime of the customer once the CFDI is
  stamped.
- The bank transaction receipt also shows the XML VAT, the payment method,
  the memo, the fiscal regime of the customer and the bank accounts of the
  CFDI payment node, and its PDF is named after the journal entry
  (`Payment Receipt - BNK1/2026/00001`).
- The CFDI documents of an invoice get a *Send Payment Receipt* button that
  opens the email composer with the receipt: the payment receipt template
  of the payment or, for a bank transaction, a template that attaches the
  receipt and the CFDI XML.
- The *Print* button of the CFDI documents is also available for PUE
  payments.
- The bank reconciliation list has an optional *Fiscal Folio* column.
