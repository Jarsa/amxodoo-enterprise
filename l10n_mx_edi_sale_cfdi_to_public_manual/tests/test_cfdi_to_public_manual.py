from odoo import Command
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
        cls.env.user.group_ids |= cls.env.ref("sales_team.group_sale_salesman")
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

    def test_new_order_without_customer_keeps_box_unchecked(self):
        order = self.env["sale.order"].new({})
        self.assertFalse(order.l10n_mx_edi_cfdi_to_public)

    def test_foreign_customer_keeps_box_unchecked(self):
        # Since 20.0 upstream also ticks the box for every foreign customer,
        # even when its fiscal data is complete.
        partner_us = self.env["res.partner"].create(
            {
                "name": "Foreign customer",
                "country_id": self.env.ref("base.us").id,
                "zip": "39301",
                "vat": "123456789",
            }
        )
        order = self._new_order(partner_us)
        self.assertFalse(order.l10n_mx_edi_cfdi_to_public)

    def test_created_invoice_keeps_box_unchecked(self):
        # Upstream ticks the box on the invoice too when the customer has no
        # VAT; the value coming from the sale order must win.
        partner_no_vat = self.partner_mx.copy({"vat": False})
        order = self.env["sale.order"].create(
            {
                "partner_id": partner_no_vat.id,
                "order_line": [
                    Command.create({"product_id": self.product.id, "price_unit": 100.0})
                ],
            }
        )
        order.action_confirm()
        order.order_line.qty_delivered = 1
        invoice = order._create_invoices()
        self.assertFalse(invoice.l10n_mx_edi_cfdi_to_public)

    def test_invoice_inherits_unchecked_box(self):
        order = self._new_order(self.partner_incomplete)
        self.assertFalse(order._prepare_invoice()["l10n_mx_edi_cfdi_to_public"])

    def test_disable_param_gives_the_standard_compute_back(self):
        # With the kill switch on, upstream owns the field again and
        # overwrites the manual tick on the next recompute. The compute is
        # called explicitly because the upstream triggers changed across
        # 17.0 releases.
        self.env["ir.config_parameter"].sudo().set_str(DISABLE_PARAM, "1")
        order = self._new_order(self.partner_mx)
        order.l10n_mx_edi_cfdi_to_public = True
        order._compute_l10n_mx_edi_cfdi_to_public()
        self.assertFalse(order.l10n_mx_edi_cfdi_to_public)

    def test_disable_param_off_keeps_box_unchecked(self):
        self.env["ir.config_parameter"].sudo().set_str(DISABLE_PARAM, "0")
        order = self._new_order(self.partner_incomplete)
        self.assertFalse(order.l10n_mx_edi_cfdi_to_public)
