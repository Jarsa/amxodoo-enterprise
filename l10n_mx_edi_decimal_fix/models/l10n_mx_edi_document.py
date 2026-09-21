from odoo import api, models
from odoo.tools.float_utils import float_is_zero, float_round


class L10nMxEdiDocument(models.Model):
    _inherit = "l10n_mx_edi.document"

    @api.model
    def _add_currency_cfdi_values(self, cfdi_values, currency):
        res = super()._add_currency_cfdi_values(cfdi_values, currency)
        currency_precision = currency.l10n_mx_edi_decimal_places

        def format_float(
            amount, precision=currency_precision, rounding="HALF-UP", min_precision=None
        ):
            if amount is None or amount is False:
                return None
            rounded = float_round(
                amount, precision_digits=precision, rounding_method=rounding
            )
            if float_is_zero(rounded, precision_digits=precision):
                rounded = 0.0
            res = "%.*f" % (precision, rounded)
            if min_precision is not None:
                # Drop the trailing zeros beyond min_precision: "28200.000000"
                # -> "28200.00", "18796.718750" -> "18796.71875".
                integer, decimals = res.split(".")
                res = f"{integer}.{decimals.rstrip('0').ljust(min_precision, '0')}"
            return res

        cfdi_values.update(
            {
                "format_float": format_float,
                "currency_precision": currency_precision,
            }
        )
        return res

    @api.model
    def _get_post_fix_tax_amounts_map(
        self, base_amount, tax_amount, tax_rate, precision_digits
    ):
        if (
            float_round(
                abs(base_amount * tax_rate - tax_amount),
                precision_digits,
                rounding_method="HALF-UP",
            )
            == 0.0
        ):
            # No arithmetic inconsistency at precision_digits — return values
            # unchanged so that delta_base_amount is exactly 0.0. Returning a
            # float-rounded new_base would produce a different IEEE-754
            # double than base_amount, generating a sub-epsilon negative delta
            # that, when added to gross_price_subtotal (which may be a third
            # distinct double), pushes importe below the ROUND_HALF_UP midpoint.
            return {
                "new_base_amount": base_amount,
                "new_tax_amount": tax_amount,
                "delta_base_amount": 0.0,
                "delta_tax_amount": 0.0,
            }

        # HALF-UP, never UP: the SAT accepts ImporteDR only within
        # [trunc(BaseDR * Tasa), ceil(BaseDR * Tasa)] (CRP20261). Rounding the
        # base up moves up to one unit from importe to base, which can push
        # importe below the lower limit (7793.24 / 1.16 = 6718.3103 -> UP gives
        # 6718.32 / 1074.92 but 6718.32 * 0.16 = 1074.9312 -> min 1074.93).
        total = base_amount + tax_amount
        new_base_amount = float_round(
            total / (1 + tax_rate),
            precision_digits=precision_digits,
            rounding_method="HALF-UP",
        )
        new_tax_amount = total - new_base_amount
        return {
            "new_base_amount": new_base_amount,
            "new_tax_amount": new_tax_amount,
            "delta_base_amount": new_base_amount - base_amount,
            "delta_tax_amount": new_tax_amount - tax_amount,
        }
