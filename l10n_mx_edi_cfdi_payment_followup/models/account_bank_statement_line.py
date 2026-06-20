from odoo import _, models
from odoo.exceptions import UserError


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

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
