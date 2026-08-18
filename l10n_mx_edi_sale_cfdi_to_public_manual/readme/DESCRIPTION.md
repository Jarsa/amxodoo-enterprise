Since Odoo 17.4, `l10n_mx_edi_sale` computes the *CFDI to Public* checkbox of a
sale order from the customer fiscal address: the box is ticked whenever the
customer has no country, zip code and VAT. As a new order has no customer yet,
users see the box already ticked while creating the order, and it stays ticked
for foreign customers, whose RFC is usually not captured.

If the order is invoiced with that box ticked, the CFDI is stamped to
*PUBLICO EN GENERAL* (RFC `XAXX010101000`) instead of the customer RFC, and the
invoice has to be cancelled and stamped again.

This module restores the previous behaviour: the checkbox always starts
unchecked and is only ticked when a user does it explicitly. The value is still
copied to the invoice created from the sale order.
