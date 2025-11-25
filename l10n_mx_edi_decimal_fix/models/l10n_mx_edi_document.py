from odoo import api, models
from odoo.tools.float_utils import float_round


class L10nMxEdiDocument(models.Model):
    _inherit = "l10n_mx_edi.document"

    @api.model
    def _add_base_cfdi_values(self, cfdi_values):
        res = super()._add_base_cfdi_values(cfdi_values)
        res["float_round"] = float_round
        return res
