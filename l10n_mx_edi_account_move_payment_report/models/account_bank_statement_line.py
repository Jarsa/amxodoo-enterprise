from odoo import fields, models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    l10n_mx_edi_cfdi_uuid = fields.Char(related="move_id.l10n_mx_edi_cfdi_uuid", string="Fiscal Folio", readonly=True, store=True)
