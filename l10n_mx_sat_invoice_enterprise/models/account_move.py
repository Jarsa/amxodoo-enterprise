# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import Command, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_mx_sat_link_by_fiscal_folio(self):
        """Link the invoices that have a fiscal folio to the downloaded CFDI
        of that folio, when it is not linked to another invoice.

        Silent: it runs when the CFDIs are downloaded and when the invoices
        are stamped, nothing is attached nor posted.
        """
        Document = self.env["l10n_mx_sat.document"].sudo()
        for move in self:
            uuid = move.l10n_mx_edi_cfdi_uuid
            if (
                not uuid
                or move.l10n_mx_sat_document_id
                or not move.is_invoice()
                or move.state == "cancel"
            ):
                continue
            document = Document.search(
                [
                    ("company_id", "=", move.company_id.id),
                    ("document_kind", "=", "cfdi"),
                    (
                        "direction",
                        "=",
                        "issued" if move.is_sale_document() else "received",
                    ),
                    ("uuid", "=ilike", uuid),
                    ("vendor_bill_id", "=", False),
                    ("customer_invoice_id", "=", False),
                ],
                limit=1,
            )
            if document:
                document._link_invoice(move)
                move.l10n_mx_sat_document_id = document

    def _l10n_mx_sat_link_candidate(self, domain):
        # A stamped or received invoice is linked to the CFDI of its folio
        if self.l10n_mx_edi_cfdi_uuid:
            return self.env["l10n_mx_sat.document"].search(
                [*domain, ("uuid", "=ilike", self.l10n_mx_edi_cfdi_uuid)], limit=1
            )
        return super()._l10n_mx_sat_link_candidate(domain)

    def _l10n_mx_sat_after_import(self, tree, document, attachment):
        if self.l10n_mx_edi_cfdi_uuid:
            # Existing invoice linked to the CFDI of its own fiscal folio:
            # it is already stamped or received, nothing to register.
            return super()._l10n_mx_sat_after_import(tree, document, attachment)
        # Written once the lines exist: the payment policy is recomputed from
        # the payment terms when the lines change.
        vals = {
            "l10n_mx_edi_payment_method_id": self.env["l10n_mx_edi.payment.method"]
            .search([("code", "=", tree.get("FormaPago"))], limit=1)
            .id,
        }
        for field, value in (
            ("l10n_mx_edi_payment_policy", tree.get("MetodoPago")),
            ("l10n_mx_edi_usage", tree.find("{*}Receptor").get("UsoCFDI")),
        ):
            if value in dict(self._fields[field].selection):
                vals[field] = value
        related = tree.find("{*}CfdiRelacionados")
        if related is not None:
            uuids = ",".join(
                node.get("UUID") for node in related.findall("{*}CfdiRelacionado")
            )
            vals["l10n_mx_edi_cfdi_origin"] = f"{related.get('TipoRelacion')}|{uuids}"
        self.write(vals)
        # The EDI document marks the invoice as stamped (issued) or received,
        # gives it the fiscal folio and the SAT status.
        # The invoice is linked by the caller, not by its fiscal folio
        self.env["l10n_mx_edi.document"].with_context(
            l10n_mx_sat_no_auto_link=True
        ).create(
            {
                "move_id": self.id,
                "invoice_ids": [Command.set(self.ids)],
                "state": "invoice_sent"
                if self.is_sale_document()
                else "invoice_received",
                "sat_state": "valid"
                if document.sat_status == "valid"
                else "not_defined",
                "attachment_id": attachment.id,
                "datetime": fields.Datetime.now(),
            }
        )
        return super()._l10n_mx_sat_after_import(tree, document, attachment)
