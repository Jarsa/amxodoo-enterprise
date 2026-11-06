# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models


class L10nMxSatPayment(models.Model):
    _inherit = "l10n_mx_sat.payment"

    def _after_apply(self, payment, invoices):
        res = super()._after_apply(payment, invoices)
        document = self.document_id
        move = payment.move_id
        if self.payment_form and not move.l10n_mx_edi_payment_method_id:
            move.l10n_mx_edi_payment_method_id = self.env[
                "l10n_mx_edi.payment.method"
            ].search([("code", "=", self.payment_form)], limit=1)
        # The payment CFDI of an issued complement is already stamped: register
        # it so the payment is not sent again. Received complements have no
        # EDI document state in l10n_mx_edi.
        if document.direction == "issued" and not move.l10n_mx_edi_cfdi_uuid:
            edi_document = move._l10n_mx_edi_cfdi_payment_document_sent(
                invoices,
                document.attachment_id.name or f"{document.uuid}.xml",
                document.attachment_id.with_context(bin_size=False).raw,
            )
            if document.sat_status == "valid":
                edi_document.sat_state = "valid"
        return res


class L10nMxSatPaymentLine(models.Model):
    _inherit = "l10n_mx_sat.payment.line"

    def _find_invoice(self):
        invoice = super()._find_invoice()
        if invoice:
            return invoice
        document = self.payment_id.document_id
        return self.env["account.move"].search(
            [
                ("company_id", "=", document.company_id.id),
                ("l10n_mx_edi_cfdi_uuid", "=ilike", self.uuid),
                (
                    "move_type",
                    "in",
                    ("out_invoice", "out_refund")
                    if document.direction == "issued"
                    else ("in_invoice", "in_refund"),
                ),
            ],
            limit=1,
        )
