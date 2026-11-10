# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class L10nMxSatDocument(models.Model):
    _inherit = "l10n_mx_sat.document"

    def _upsert_from_xml(self, tree, xml_bytes, company, request):
        document = super()._upsert_from_xml(tree, xml_bytes, company, request)
        document._l10n_mx_sat_link_invoice_by_fiscal_folio()
        return document

    def _l10n_mx_sat_link_invoice_by_fiscal_folio(self):
        """Link the CFDIs to the invoice that already has their fiscal folio
        (stamped in Odoo or received with its XML)."""
        documents = self.filtered(
            lambda d: d.document_kind == "cfdi"
            and d.voucher_type in ("I", "E")
            and not d.invoice_id
        )
        if not documents:
            return
        # Folios are stored in upper case by the SAT and by the stamping
        self.env["account.move"].sudo().search(
            [
                ("company_id", "in", documents.company_id.ids),
                ("l10n_mx_edi_cfdi_uuid", "in", documents.mapped("uuid")),
                ("l10n_mx_sat_document_id", "=", False),
                ("state", "!=", "cancel"),
            ]
        )._l10n_mx_sat_link_by_fiscal_folio()

    def _l10n_mx_sat_invoice_rejection(self, move=None):
        rejection = super()._l10n_mx_sat_invoice_rejection(move=move)
        if rejection:
            return rejection
        domain = [
            ("company_id", "=", self.company_id.id),
            ("l10n_mx_edi_cfdi_uuid", "=ilike", self.uuid),
            ("state", "!=", "cancel"),
        ]
        if move:
            # Linking an existing invoice: it may already hold this folio
            move_uuid = move.l10n_mx_edi_cfdi_uuid
            if move_uuid and move_uuid.upper() != self.uuid.upper():
                return self.env._(
                    "%(move)s has the fiscal folio %(move_uuid)s, different "
                    "from the CFDI %(uuid)s.",
                    move=move.display_name,
                    move_uuid=move_uuid,
                    uuid=self.uuid,
                )
            domain.append(("id", "!=", move.id))
        duplicate = self.env["account.move"].search(domain, limit=1)
        if duplicate:
            return self.env._(
                "The fiscal folio %(uuid)s is already registered in %(move)s.",
                uuid=self.uuid,
                move=duplicate.display_name,
            )
        status = self._l10n_mx_sat_invoice_fetch_sat_status()
        if status == "cancelled":
            return self.env._("%(uuid)s is cancelled in the SAT.", uuid=self.uuid)
        if status == "not_found":
            return self.env._("%(uuid)s was not found in the SAT.", uuid=self.uuid)
        return False

    def _l10n_mx_sat_invoice_fetch_sat_status(self):
        """Ask the SAT for the status of the CFDI and store it.

        :return: ``valid``, ``cancelled``, ``not_found``, ``not_defined`` or
            ``error`` (the SAT could not be reached).
        """
        self.ensure_one()
        result = self.env["l10n_mx_edi.document"]._fetch_sat_status(
            self.issuer_rfc, self.receiver_rfc, self.total, self.uuid
        )
        status = result["value"]
        if status == "error":
            _logger.warning("%s: %s", self.uuid, result.get("error"))
        elif status in ("valid", "cancelled") and status != self.sat_status:
            self._sat_write({"sat_status": status})
        return status
