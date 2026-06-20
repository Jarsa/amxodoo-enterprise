from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    l10n_mx_edi_cfdi_payment_receipt = fields.Binary(
        related="move_id.l10n_mx_edi_cfdi_payment_receipt",
        readonly=False,
    )
    l10n_mx_edi_cfdi_payment_receipt_filename = fields.Char(
        string="Payment Receipt Filename",
        related="move_id.l10n_mx_edi_cfdi_payment_receipt_filename",
        readonly=False,
    )

    def action_open_receipt_wizard(self):
        self.ensure_one()
        return {
            "name": "Upload Payment Receipt",
            "type": "ir.actions.act_window",
            "res_model": "account.bank.statement.line",
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref(
                "l10n_mx_edi_cfdi_payment_followup.view_bank_statement_line_form_receipt_upload"
            ).id,
            "target": "new",
        }

    def action_request_cfdi_complement(self):
        return self.move_id.action_request_cfdi_complement()

    def action_cfdi_payment_followup(self):
        return self.move_id.action_cfdi_payment_followup()

    def action_cfdi_ignore(self):
        return self.move_id.action_cfdi_ignore()

    def action_cfdi_unignore(self):
        return self.move_id.action_cfdi_unignore()

    def action_request_cfdi_complement_mass(self):
        targets = self.filtered(
            lambda r: r.l10n_mx_edi_cfdi_is_supplier_payment
            and r.l10n_mx_edi_cfdi_payment_state in ("pending", "requested")
        )
        if not targets:
            raise UserError(
                _(
                    "No selected bank statement lines are in 'Pending' or "
                    "'Requested' state. Mass reminders can only be sent for "
                    "lines awaiting a CFDI payment complement."
                )
            )
        targets.move_id.action_request_cfdi_complement()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": _("CFDI complement reminders sent for %d payment(s).")
                % len(targets),
                "sticky": False,
            },
        }
