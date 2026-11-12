from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    # Payments no longer inherit their journal entry, so the follow-up fields
    # of the entry are exposed here as related fields.
    l10n_mx_edi_cfdi_payment_state = fields.Selection(
        related="move_id.l10n_mx_edi_cfdi_payment_state",
    )
    l10n_mx_edi_cfdi_payment_last_followup_date = fields.Datetime(
        related="move_id.l10n_mx_edi_cfdi_payment_last_followup_date",
    )
    l10n_mx_edi_cfdi_is_supplier_payment = fields.Boolean(
        related="move_id.l10n_mx_edi_cfdi_is_supplier_payment",
    )
    l10n_mx_edi_cfdi_payment_receipt = fields.Binary(
        related="move_id.l10n_mx_edi_cfdi_payment_receipt",
        readonly=False,
    )
    l10n_mx_edi_cfdi_payment_receipt_filename = fields.Char(
        related="move_id.l10n_mx_edi_cfdi_payment_receipt_filename",
        readonly=False,
    )

    def action_request_cfdi_complement(self):
        return self.move_id.action_request_cfdi_complement()

    def action_cfdi_ignore(self):
        return self.move_id.action_cfdi_ignore()

    def action_cfdi_unignore(self):
        return self.move_id.action_cfdi_unignore()

    def _message_post_after_hook(self, message):
        res = super()._message_post_after_hook(message)
        if self.move_id:
            for attachment in message.attachment_ids:
                self.move_id._process_cfdi_payment_xml(attachment)
        return res
