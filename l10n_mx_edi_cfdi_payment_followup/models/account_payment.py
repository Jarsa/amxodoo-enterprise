from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def action_request_cfdi_complement(self):
        return self.move_id.action_request_cfdi_complement()

    def _message_post_after_hook(self, new_message, message_values):
        res = super()._message_post_after_hook(new_message, message_values)
        for attachment in new_message.attachment_ids:
            self.move_id._process_cfdi_payment_xml(attachment)
        return res
