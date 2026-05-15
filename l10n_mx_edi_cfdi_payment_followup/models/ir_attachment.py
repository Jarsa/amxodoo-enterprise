from odoo import models


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _post_add_create(self, **kwargs):
        res = super()._post_add_create(**kwargs)
        for attachment in self:
            if attachment.res_model != "account.move" or not attachment.res_id:
                continue
            move = self.env["account.move"].browse(attachment.res_id).exists()
            if move:
                move._process_cfdi_payment_xml(attachment)
        return res
