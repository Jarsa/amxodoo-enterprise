Use **Create Invoice** on the SAT documents as described in
`l10n_mx_sat_invoice`. The created invoices show the fiscal folio and the SAT
status in the **MX EDI** section.

**Link SAT CFDI** on an existing invoice also registers the fiscal folio of
the chosen CFDI. An invoice that already has a fiscal folio (stamped in Odoo
or received) can only be linked to the CFDI of that folio, which is proposed
by the wizard.

## Bank reconciliation

In the bank reconciliation, the menu (⋮) of a transaction has the option
**Create from SAT CFDIs**, next to **Upload Bills**:

1. The wizard takes the direction from the transaction: money out pays
   vendor bills (received CFDIs), money in pays customer invoices (issued
   CFDIs).
2. Add the CFDIs paid by the transaction. Only invoices (type I) without
   invoice in Odoo are listed, filtered by the RFC of the partner of the
   transaction; uncheck **Only CFDIs of the partner** to list all of them.
   The total of the selected CFDIs and the difference with the transaction
   are shown below the list.
3. Check the journal and the account and click **Create and Match**: the
   invoices are created as with **Create Invoice** and matched with the
   transaction. When the CFDIs add up to more than the transaction, the last
   one is left partially paid.

## Automatic link by fiscal folio

An invoice that has a fiscal folio (stamped in Odoo or received with its
XML) is linked to the downloaded CFDI of that folio without any action:
when the CFDI is downloaded from the SAT and when the invoice gets its
folio. The **Link SAT CFDI** button is hidden on those invoices; it is meant
for the invoices without fiscal folio. Updating the module links the
existing invoices.
