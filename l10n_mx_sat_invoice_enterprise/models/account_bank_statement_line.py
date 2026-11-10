# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    def action_l10n_mx_sat_create_invoices(self):
        """Wizard of the bank reconciliation to create the invoices paid by
        the transaction from the CFDIs downloaded from the SAT."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Create Invoices from SAT CFDIs"),
            "res_model": "l10n_mx_sat.statement.line.wizard",
            "view_mode": "form",
            # Called by the bank reconciliation through RPC: no clean_action
            "views": [(False, "form")],
            "target": "new",
            "context": {"default_statement_line_id": self.id},
        }
