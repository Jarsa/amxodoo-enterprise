from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from odoo import api, models


class L10nMxEdiDocument(models.Model):
    _inherit = "l10n_mx_edi.document"

    @api.model
    def _add_currency_cfdi_values(self, cfdi_values, currency):
        res = super()._add_currency_cfdi_values(cfdi_values, currency)
        currency_precision = currency.l10n_mx_edi_decimal_places

        def format_float(amount, precision=2):
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
                "currency_precision": currency_precision,
            }
        )
        return res

    @api.model
    def _get_post_fix_tax_amounts_map(
        self, base_amount, tax_amount, tax_rate, precision_digits
    ):
        qty = Decimal("1." + ("0" * precision_digits))
        d_base = Decimal(str(base_amount))
        d_tax = Decimal(str(tax_amount))
        d_rate = Decimal(str(tax_rate))

        mismatch = (d_base * d_rate - d_tax).copy_abs().quantize(
            qty, rounding=ROUND_DOWN
        )
        if mismatch == Decimal("0"):
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

        d_total = d_base + d_tax
        new_base = float((d_total / (1 + d_rate)).quantize(qty, rounding=ROUND_HALF_UP))
        new_tax = float(d_total - Decimal(str(new_base)))
        return {
            "new_base_amount": new_base,
            "new_tax_amount": new_tax,
            "delta_base_amount": new_base - base_amount,
            "delta_tax_amount": new_tax - tax_amount,
        }

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
