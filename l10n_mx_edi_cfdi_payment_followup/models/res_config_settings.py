from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_mx_edi_cfdi_payment_start_date = fields.Date(
        string="CFDI Payment Follow-up Start Date",
        related="company_id.l10n_mx_edi_cfdi_payment_start_date",
        readonly=False,
    )
    l10n_mx_edi_cfdi_responsible_team_id = fields.Many2one(
        comodel_name="mail.activity.team",
        string="CFDI Follow-up Responsible Team",
        related="company_id.l10n_mx_edi_cfdi_responsible_team_id",
        readonly=False,
    )
    l10n_mx_edi_cfdi_payment_cc_user_ids = fields.Many2many(
        comodel_name="res.users",
        related="company_id.l10n_mx_edi_cfdi_payment_cc_user_ids",
        readonly=False,
    )
