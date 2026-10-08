# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class L10nMxSatDocument(models.Model):
    _inherit = "l10n_mx_sat.document"

    @api.model
    def _get_selectable_domain(self, company, partner=None, currency=None):
        domain = super()._get_selectable_domain(
            company, partner=partner, currency=currency
        )
        used_uuids = self._get_used_fiscal_folios(company)
        if used_uuids:
            domain.append(("uuid", "not in", used_uuids))
        return domain

    @api.model
    def _get_used_fiscal_folios(self, company):
        """Fiscal folios already registered in a vendor bill of ``company``."""
        moves = self.env["account.move"].search_fetch(
            [
                ("company_id", "=", company.id),
                ("move_type", "in", ("in_invoice", "in_refund")),
                ("state", "!=", "cancel"),
                ("l10n_mx_edi_cfdi_uuid", "!=", False),
            ],
            ["l10n_mx_edi_cfdi_uuid"],
        )
        return [uuid.upper() for uuid in moves.mapped("l10n_mx_edi_cfdi_uuid")]

    def _fetch_sat_status(self):
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

    def _link_vendor_bill(self, move):
        super()._link_vendor_bill(move)
        if move.l10n_mx_edi_cfdi_uuid != self.uuid:
            _logger.warning(
                "The CFDI %s was not imported in %s, check the chatter of the bill.",
                self.uuid,
                move.display_name,
            )
            return
        if self.sat_status == "valid":
            # The status was just fetched, no need to wait for the cron.
            for document in move.l10n_mx_edi_document_ids.filtered(
                lambda d: d.state == "invoice_received" and d.sat_state != "valid"
            ):
                document._update_document_sat_state("valid")
