Bridge between `l10n_mx_sat_payment` and `l10n_mx_edi`: the payments applied
from the SAT payment complements get the payment method of the complement and,
for issued complements, the stamped payment CFDI as their EDI document, so Odoo
does not stamp a second payment complement for them. The invoices paid by a
complement are also found by their fiscal folio.
