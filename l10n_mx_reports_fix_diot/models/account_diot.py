from odoo import models

class MexicanAccountReportCustomHandler(models.AbstractModel):
    _inherit = 'l10n_mx.report.handler'

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
        for partner, data in diot_values.items():
            for label, value in data.items():
                if value and isinstance(value, float):
                    diot_values[partner][label] = int(value)
        return diot_values
