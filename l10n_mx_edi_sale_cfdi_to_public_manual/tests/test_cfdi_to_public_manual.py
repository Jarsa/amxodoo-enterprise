from odoo.tests import tagged

from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon


@tagged("post_install_l10n", "post_install", "-at_install")
class TestCfdiToPublicManual(TestMxEdiCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_incomplete = cls.env["res.partner"].create(
            {"name": "Cliente sin datos fiscales"}
        )

    def _new_order(self, partner):
        return self.env["sale.order"].create({"partner_id": partner.id})

    def test_incomplete_partner_keeps_box_unchecked(self):
        order = self._new_order(self.partner_incomplete)
        self.assertFalse(order.l10n_mx_edi_cfdi_to_public)

    def test_recompute_keeps_box_unchecked(self):
        order = self._new_order(self.partner_mx)
        order.partner_id = self.partner_incomplete
        order.invalidate_recordset()
        self.assertFalse(order.l10n_mx_edi_cfdi_to_public)

    def test_manual_check_survives_partner_change(self):
        order = self._new_order(self.partner_mx)
        order.l10n_mx_edi_cfdi_to_public = True
        order.partner_id = self.partner_incomplete
        self.assertTrue(order.l10n_mx_edi_cfdi_to_public)

    def test_invoice_inherits_unchecked_box(self):
        order = self._new_order(self.partner_incomplete)
        self.assertFalse(order._prepare_invoice()["l10n_mx_edi_cfdi_to_public"])
