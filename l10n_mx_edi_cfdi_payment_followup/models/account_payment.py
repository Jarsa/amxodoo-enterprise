from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def action_request_cfdi_complement(self):
        return self.move_id.action_request_cfdi_complement()
