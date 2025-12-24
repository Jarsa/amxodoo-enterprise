from odoo import api, models
from odoo.tools.float_utils import float_is_zero, float_round
from decimal import Decimal, ROUND_HALF_UP


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

            qty = Decimal('1.' + ('0' * precision))
            value = Decimal(str(amount))

            return format(
                value.quantize(qty, rounding=ROUND_HALF_UP),
                f'.{precision}f'
            )

        cfdi_values.update({
            'format_float': format_float,
        })
        return res
