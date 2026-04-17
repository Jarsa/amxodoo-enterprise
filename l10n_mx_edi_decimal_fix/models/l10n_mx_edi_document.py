from decimal import ROUND_HALF_UP, Decimal

from odoo import api, models
from odoo.tools.float_utils import float_round


class L10nMxEdiDocument(models.Model):
    _inherit = "l10n_mx_edi.document"

    @api.model
    def _add_base_cfdi_values(self, cfdi_values):
        cfdi_values["float_round"] = float_round
        return super()._add_base_cfdi_values(cfdi_values)

    @api.model
    def _add_currency_cfdi_values(self, cfdi_values, currency):
        res = super()._add_currency_cfdi_values(cfdi_values, currency)
        currency_precision = currency.l10n_mx_edi_decimal_places

        def format_float(amount, precision=currency_precision):
            if amount is None:
                return None

            if amount is False:
                amount = 0

            qty = Decimal("1." + ("0" * precision))
            value = Decimal(str(amount))

            return format(value.quantize(qty, rounding=ROUND_HALF_UP), f".{precision}f")

        cfdi_values.update(
            {
                "format_float": format_float,
            }
        )
        return res

    @api.model
    def _get_company_cfdi_values(self, company):
        res = super()._get_company_cfdi_values(company)
        if self._context.get("params", {}).get("model") == "account.move":
            move = self.env["account.move"].browse(
                self._context.get("params", {}).get("id")
            )
            if move and move.journal_id.l10n_mx_address_issued_id != res.get(
                "issued_address"
            ):
                res["issued_address"] = move.journal_id.l10n_mx_address_issued_id
        return res
