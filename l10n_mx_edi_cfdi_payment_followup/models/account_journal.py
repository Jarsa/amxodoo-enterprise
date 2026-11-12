from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_mx_edi_cfdi_payment_followup = fields.Boolean(
        string="Requires CFDI Payment Complement",
        help="Only payments registered in journals with this option enabled are "
        "tracked for the CFDI payment complement follow-up. Leave it off for "
        "credit cards, clearing journals or any other journal whose payments "
        "never require a complement.",
    )
