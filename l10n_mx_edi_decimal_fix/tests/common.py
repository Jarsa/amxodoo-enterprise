from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon


class TestDecimalFixCommon(TestMxEdiCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.mxn_currency = cls.env.ref("base.MXN")
        cls.mxn_currency.sudo().write(
            {
                "l10n_mx_edi_decimal_places": 6,
                "rounding": 0.000001,
            }
        )
        cls.usd_currency = cls.env.ref("base.USD")
        cls.usd_currency.sudo().write(
            {
                "l10n_mx_edi_decimal_places": 6,
                "rounding": 0.000001,
            }
        )
