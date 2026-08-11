import math

from odoo import models


# SAT rounding rule: decimals <= .50 go down, > .50 go up.
def sat_round(value):
    decimal = round(value - math.floor(value), 2)
    return math.floor(value) if decimal <= 0.50 else math.ceil(value)


# SAT validates every VAT column against the already-rounded base, so the VAT
# must be recomputed as rounded_base * rate instead of rounding the VAT coming
# from accounting (e.g. base 5,006.42 -> 5,006; 5,006 * 0.08 = 400.48 -> 400,
# while rounding the accounting VAT 400.51 would wrongly report 401).
TAX_BASE_RATE = {
    "paid_8_tax": ("paid_8", 0.08),
    "paid_8_non_cred_tax": ("paid_8_non_cred", 0.08),
    "paid_8_s_tax": ("paid_8_s", 0.08),
    "paid_8_s_nc_tax": ("paid_8_s_nc", 0.08),
    "paid_16_tax": ("paid_16", 0.16),
    "paid_16_non_cred_tax": ("paid_16_non_cred", 0.16),
    "importation_16_tax": ("importation_16", 0.16),
    "paid_16_imp_nc_tax": ("paid_16_imp_nc", 0.16),
    "paid_16_imp_int_tax": ("paid_16_imp_int", 0.16),
    "paid_16_imp_int_nc_tax": ("paid_16_imp_int_nc", 0.16),
}


class MexicanAccountReportCustomHandler(models.AbstractModel):
    _inherit = "l10n_mx.report.handler"

    def l10n_mx_diot_get_values(self, values, data, partner):
        res = super().l10n_mx_diot_get_values(values, data, partner)
        if data[27]:
            data[28] = data[27]
            data[27] = 0
        if data[31]:
            data[32] = data[31]
            data[31] = 0
        if data[35]:
            data[36] = data[35]
            data[35] = 0
        if data[39]:
            data[40] = data[39]
            data[39] = 0
        if data[43]:
            data[44] = data[43]
            data[43] = 0
        return res

    def _get_diot_values_per_partner(self, report, options):
        diot_values = super()._get_diot_values_per_partner(report, options)
        for data in diot_values.values():
            originals = dict(data)
            for label, value in data.items():
                if value and isinstance(value, float):
                    data[label] = sat_round(value)
            for tax_label, (base_label, rate) in TAX_BASE_RATE.items():
                tax = originals.get(tax_label)
                base = originals.get(base_label)
                if (
                    not tax
                    or not base
                    or not isinstance(tax, float)
                    or not isinstance(base, float)
                ):
                    continue
                # Recompute only when the accounting VAT already matches
                # base * rate up to per-invoice cent drift; with partially
                # creditable VAT the accounting amount must be kept as is.
                # ponytail: 0.5 tolerance covers ~100 invoices of half-cent
                # drift per partner; raise it if a partner ever exceeds that.
                if abs(base * rate - tax) <= 0.5:
                    data[tax_label] = sat_round(sat_round(base) * rate)
        return diot_values
