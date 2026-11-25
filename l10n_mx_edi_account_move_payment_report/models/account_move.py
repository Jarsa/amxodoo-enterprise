from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _process_attachments_for_template_post(self, mail_template):
        """Attach the CFDI XML to the payment receipt of a bank transaction."""
        result = super()._process_attachments_for_template_post(mail_template)
        template = self.env.ref(
            "l10n_mx_edi_account_move_payment_report."
            "mail_template_data_bank_transaction_receipt",
            raise_if_not_found=False,
        )
        if mail_template != template:
            return result
        for move in self.filtered("l10n_mx_edi_cfdi_attachment_id"):
            move_result = result.setdefault(move.id, {})
            move_result.setdefault("attachment_ids", []).append(
                move.l10n_mx_edi_cfdi_attachment_id.id
            )
        return result

    def _get_payment_receipt_report_filename(self):
        """File name of the payment receipt of a bank transaction."""
        self.ensure_one()
        return self.env._("Payment Receipt - %s", self.name)
