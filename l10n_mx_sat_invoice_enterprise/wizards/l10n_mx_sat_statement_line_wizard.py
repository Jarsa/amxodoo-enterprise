# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class L10nMxSatStatementLineWizard(models.TransientModel):
    _name = "l10n_mx_sat.statement.line.wizard"
    _inherit = "l10n_mx_sat.invoice.wizard"
    _description = "Create the invoices of a bank transaction from SAT CFDIs"

    statement_line_id = fields.Many2one(
        comodel_name="account.bank.statement.line",
        string="Bank transaction",
        required=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency", compute="_compute_amounts"
    )
    amount = fields.Monetary(string="Transaction amount", compute="_compute_amounts")
    selected_total = fields.Float(
        string="Total of the CFDIs", digits=(16, 2), compute="_compute_amounts"
    )
    difference = fields.Monetary(compute="_compute_amounts")
    same_currency = fields.Boolean(compute="_compute_amounts")
    partner_id = fields.Many2one(related="statement_line_id.partner_id")
    only_partner = fields.Boolean(
        string="Only CFDIs of the partner",
        default=True,
        help="Show only the CFDIs with the RFC of the partner of the transaction.",
    )
    document_domain = fields.Binary(compute="_compute_document_domain")

    @api.depends("statement_line_id")
    def _compute_from_documents(self):
        # The transaction, not the CFDIs, tells what is being paid: money out
        # pays vendor bills (received CFDIs), money in customer invoices.
        for wizard in self:
            line = wizard.statement_line_id
            issued = line.amount > 0
            wizard.company_id = line.company_id
            wizard.direction = "issued" if issued else "received"
            wizard.journal_type = "sale" if issued else "purchase"

    @api.depends("statement_line_id", "document_ids")
    def _compute_amounts(self):
        for wizard in self:
            line = wizard.statement_line_id
            documents = wizard.document_ids
            wizard.currency_id = line.foreign_currency_id or line.currency_id
            wizard.amount = abs(
                line.amount_currency if line.foreign_currency_id else line.amount
            )
            wizard.selected_total = sum(documents.mapped("total"))
            wizard.same_currency = set(documents.mapped("currency_code")) <= {
                wizard.currency_id.name
            }
            wizard.difference = wizard.amount - wizard.selected_total

    @api.depends("statement_line_id", "only_partner")
    def _compute_document_domain(self):
        for wizard in self:
            line = wizard.statement_line_id
            issued = line.amount > 0
            domain = [
                ("company_id", "=", line.company_id.id),
                ("document_kind", "=", "cfdi"),
                ("has_xml", "=", True),
                ("direction", "=", "issued" if issued else "received"),
                ("voucher_type", "=", "I"),
                ("sat_status", "!=", "cancelled"),
                ("vendor_bill_id", "=", False),
                ("customer_invoice_id", "=", False),
            ]
            vat = line.partner_id.commercial_partner_id.vat
            if wizard.only_partner and vat:
                domain.append(
                    ("receiver_rfc" if issued else "issuer_rfc", "=ilike", vat)
                )
            wizard.document_domain = domain

    def action_create_invoices(self):
        """Create the invoices and match them with the bank transaction, as
        the upload of bills of the bank reconciliation does."""
        moves = self._create_invoices()
        lines = moves.line_ids.filtered(
            lambda line: line.account_id.account_type
            in ("asset_receivable", "liability_payable")
        )
        self.statement_line_id.set_line_bank_statement_line(lines.ids)
        return {"type": "ir.actions.act_window_close"}
