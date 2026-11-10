# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import api, models


class L10nMxEdiDocument(models.Model):
    _inherit = "l10n_mx_edi.document"

    @api.model_create_multi
    def create(self, vals_list):
        documents = super().create(vals_list)
        if not self.env.context.get("l10n_mx_sat_no_auto_link"):
            # An invoice just stamped or received: its CFDI may be downloaded
            (documents.move_id | documents.invoice_ids).filtered(
                lambda move: move.is_invoice()
            )._l10n_mx_sat_link_by_fiscal_folio()
        return documents
