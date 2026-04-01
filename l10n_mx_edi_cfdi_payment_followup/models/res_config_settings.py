from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_mx_edi_cfdi_payment_start_date = fields.Date(
        string="CFDI Payment Follow-up Start Date",
        related="company_id.l10n_mx_edi_cfdi_payment_start_date",
        readonly=False,
    )
    l10n_mx_edi_cfdi_responsible_user_id = fields.Many2one(
        comodel_name="res.users",
        string="CFDI Follow-up Responsible User",
        related="company_id.l10n_mx_edi_cfdi_responsible_user_id",
        readonly=False,
    )
