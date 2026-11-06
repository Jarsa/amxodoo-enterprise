# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class L10nMxSatDocument(models.Model):
    _inherit = "l10n_mx_sat.document"

    def _l10n_mx_sat_invoice_rejection(self):
        rejection = super()._l10n_mx_sat_invoice_rejection()
        if rejection:
            return rejection
        duplicate = self.env["account.move"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("l10n_mx_edi_cfdi_uuid", "=ilike", self.uuid),
                ("state", "!=", "cancel"),
            ],
            limit=1,
        )
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
