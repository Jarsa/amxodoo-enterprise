from odoo import models

# Models with their own chatter whose journal entry holds the follow-up
_MOVE_OWNER_MODELS = ("account.payment", "account.bank.statement.line")


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _post_add_create(self, **kwargs):
        res = super()._post_add_create(**kwargs)
        for attachment in self:
            if not attachment.res_id:
                continue
            if attachment.res_model == "account.move":
                move = self.env["account.move"].browse(attachment.res_id).exists()
            elif attachment.res_model in _MOVE_OWNER_MODELS:
                record = self.env[attachment.res_model].browse(attachment.res_id)
                move = record.exists().move_id
            else:
                continue
            if move:
                move._process_cfdi_payment_xml(attachment)
        return res
