from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_mx_edi_cfdi_payment_start_date = fields.Date(
        string="CFDI Payment Follow-up Start Date",
    )
    l10n_mx_edi_cfdi_responsible_user_id = fields.Many2one(
        comodel_name="res.users",
        string="CFDI Follow-up Responsible User",
    )
