# Copyright 2026 Jarsa
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_mx_edi_cfdi_payment_get_reconciled_invoice_values(self):
        # EXTENDS l10n_mx_edi
        # When a foreign currency statement line is reconciled against invoices in
        # company currency, the bank reconciliation widget keeps the counterpart
        # lines in company currency inside a foreign currency move and books the
        # difference as a write-off instead of an exchange difference move. The
        # standard code then reads the reconciled company currency amount as if it
        # were expressed in the move currency (MonedaP=USD, TipoCambioP=1). Use the
        # liquidity line, which carries the real amount received and its rate.
        results = super()._l10n_mx_edi_cfdi_payment_get_reconciled_invoice_values()
        for payment, pay_values in results.items():
            company_curr = payment.company_currency_id
            if payment.currency_id == company_curr or not payment.statement_line_id:
                continue
            counterpart_lines = payment.line_ids.filtered(
                lambda line: line.account_type
                in ("asset_receivable", "liability_payable")
            )
            if not counterpart_lines or any(
                line.currency_id != company_curr for line in counterpart_lines
            ):
                continue
            liquidity_lines = payment.statement_line_id._seek_for_lines()[0]
            liquidity_balance = abs(sum(liquidity_lines.mapped("balance")))
            liquidity_amount = abs(sum(liquidity_lines.mapped("amount_currency")))
            total_balance = sum(x["balance"] for x in pay_values["invoice_results"])
            if not (liquidity_balance and liquidity_amount and total_balance):
                continue
            # Known limit: the whole liquidity amount is split across the invoices by
            # reconciled balance; bank fees booked on the same statement line would
            # be treated as exchange difference too.
            for inv_values in pay_values["invoice_results"]:
                share = inv_values["balance"] / total_balance
                inv_values["payment_amount_currency"] = payment.currency_id.round(
                    liquidity_amount * share
                )
                inv_values["payment_exchange_balance"] = (
                    company_curr.round(liquidity_balance * share)
                    - inv_values["balance"]
                )
        return results
