from odoo import api, models


class L10nMxEdiDocument(models.Model):
    _inherit = "l10n_mx_edi.document"

    @api.depends("state")
    def _compute_print_button_needed(self):
        """Also print the payment receipt of PUE payments."""
        res = super()._compute_print_button_needed()
        self.filtered(
            lambda doc: doc.state == "payment_sent_pue"
        ).print_button_needed = True
        return res

    def action_send_payment_email(self):
        """Send by email the payment receipt printed by
        action_download_payment_receipt."""
        self.ensure_one()
        payment = self.move_id.origin_payment_id
        context = {"default_composition_mode": "comment"}
        if payment:
            record = payment
            template = self.env.ref(
                "account.mail_template_data_payment_receipt", raise_if_not_found=False
            )
            context["mail_post_autofollow"] = True
        else:
            record = self.move_id
            template = self.env.ref(
                "l10n_mx_edi_account_move_payment_report."
                "mail_template_data_bank_transaction_receipt",
                raise_if_not_found=False,
            )
        context.update(
            {
                "default_model": record._name,
                "default_res_ids": record.ids,
                "default_template_id": template.id if template else False,
            }
        )
        return {
            "name": self.env._("Send Payment Receipt"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "target": "new",
            "context": context,
        }
