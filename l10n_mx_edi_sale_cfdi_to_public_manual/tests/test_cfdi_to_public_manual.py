from odoo.tests import tagged

from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon
from odoo.addons.l10n_mx_edi_sale_cfdi_to_public_manual.models.sale_order import (
    DISABLE_PARAM,
)


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

    def test_disable_param_gives_the_standard_compute_back(self):
        # With the kill switch on, upstream owns the field again and
        # overwrites the manual tick on the next recompute. The compute is
        # called explicitly because the upstream triggers changed across
        # 17.0 releases.
        self.env["ir.config_parameter"].sudo().set_param(DISABLE_PARAM, "1")
        order = self._new_order(self.partner_mx)
        order.l10n_mx_edi_cfdi_to_public = True
        order._compute_l10n_mx_edi_cfdi_to_public()
        self.assertFalse(order.l10n_mx_edi_cfdi_to_public)

    def test_disable_param_off_keeps_box_unchecked(self):
        self.env["ir.config_parameter"].sudo().set_param(DISABLE_PARAM, "0")
        order = self._new_order(self.partner_incomplete)
        self.assertFalse(order.l10n_mx_edi_cfdi_to_public)
