from odoo import models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    def action_request_cfdi_complement(self):
        return self.move_id.action_request_cfdi_complement()

    def action_cfdi_payment_followup(self):
        return self.move_id.action_cfdi_payment_followup()
