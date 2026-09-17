from odoo import models
from odoo.tools.float_utils import float_round

# Decimals the SAT catalog supports for MonedaDR/MonedaP (MXN, USD...). The
# currency may be configured with more (6 in some databases), so it can not be
# read from l10n_mx_edi_decimal_places.
PAYMENT_TAX_DIGITS = 2


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_mx_edi_add_payment_cfdi_values(self, cfdi_values, pay_results):
        """Report BaseDR/ImporteDR with 2 decimals.

        With a 6 decimals currency the paid part of each tax keeps 6 decimals
        (ImporteDR="181.048000") while BaseP/ImporteP must be truncated to the
        decimals of MonedaP (ImporteP="181.04"), and the PAC rejects the
        difference with CRP20268/CRP20274. Rounding the DR amounts first makes
        the P amounts and the totals, all built from them, match exactly.
        """
        res = super()._l10n_mx_edi_add_payment_cfdi_values(cfdi_values, pay_results)
        doctos = cfdi_values.get("docto_relationado_list") or []
        for docto in doctos:
            for key in ("retenciones_list", "traslados_list"):
                for tax_values in docto[key]:
                    self._l10n_mx_edi_decimal_fix_round_tax_values(tax_values)
        if not doctos or cfdi_values.get("errors"):
            return res

        # The withholding amounts are not rebuilt by the template: do it here.
        pay_rate = cfdi_values["tipo_cambio"] or 1.0
        totals = {
            "001": "total_retenciones_isr",
            "002": "total_retenciones_iva",
            "003": "total_retenciones_ieps",
        }
        for tax_values in cfdi_values["retenciones_list"]:
            amounts = [
                (dr_values["importe"], docto["equivalencia"] or 1.0)
                for docto in doctos
                for dr_values in docto["retenciones_list"]
                if dr_values["impuesto"] == tax_values["impuesto"]
            ]
            tax_values["importe"] = float_round(
                sum(amount / rate for amount, rate in amounts), 6
            )
            total_key = totals.get(tax_values["impuesto"])
            if total_key:
                cfdi_values[total_key] = self.company_currency_id.round(
                    sum(amount * pay_rate / rate for amount, rate in amounts)
                )
        return res

    def _l10n_mx_edi_decimal_fix_round_tax_values(self, tax_values):
        def round_half_up(amount):
            return float_round(
                amount,
                precision_digits=PAYMENT_TAX_DIGITS,
                rounding_method="HALF-UP",
            )

        base, importe = tax_values["base"], tax_values["importe"]
        if base is not None:
            tax_values["base"] = round_half_up(base)
        if importe is None:
            return
        if base is None:
            importe = round_half_up(importe)
        else:
            # Keep BaseDR + ImporteDR equal to the rounded paid amount.
            importe = round_half_up(round_half_up(base + importe) - tax_values["base"])
        if tax_values["tipo_factor"] == "Tasa" and base is not None:
            # CRP20261: keep ImporteDR within [trunc, ceil] of BaseDR * Tasa.
            expected = float_round(tax_values["base"] * tax_values["tasa_o_cuota"], 6)
            lower = float_round(expected, PAYMENT_TAX_DIGITS, rounding_method="DOWN")
            upper = float_round(expected, PAYMENT_TAX_DIGITS, rounding_method="UP")
            importe = min(max(importe, lower), upper)
        tax_values["importe"] = importe
