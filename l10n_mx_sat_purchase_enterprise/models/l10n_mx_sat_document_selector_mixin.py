# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models


class L10nMxSatDocumentSelectorMixin(models.AbstractModel):
    _inherit = "l10n_mx_sat.document.selector.mixin"

    def _l10n_mx_sat_check_document(self):
        rejection = super()._l10n_mx_sat_check_document()
        if rejection:
            return rejection
        document = self.l10n_mx_sat_document_id
        duplicate = self.env["account.move"].search(
            [
                ("company_id", "=", document.company_id.id),
                ("l10n_mx_edi_cfdi_uuid", "=ilike", document.uuid),
                ("state", "!=", "cancel"),
            ],
            limit=1,
        )
        if duplicate:
            return self.env._(
                "The fiscal folio %(uuid)s is already registered in %(move)s.",
                uuid=document.uuid,
                move=duplicate.display_name,
            )
        status = document._fetch_sat_status()
        if status == "cancelled":
            return self.env._(
                "The CFDI %(uuid)s is cancelled in the SAT.", uuid=document.uuid
            )
        if status == "not_found":
            return self.env._(
                "The CFDI %(uuid)s was not found in the SAT.", uuid=document.uuid
            )
        return False
