# Copyright 2026 Jarsa
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
from lxml import etree

from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon

NS = {"pago20": "http://www.sat.gob.mx/Pagos20"}


@tagged("post_install_l10n", "post_install", "-at_install")
class TestStatementLineRate(TestMxEdiCommon):
    def _reconcile_st_line_with_writeoff(self, st_line, invoice):
        wizard = (
            self.env["bank.rec.widget"]
            .with_context(default_st_line_id=st_line.id)
            .new({})
        )
        inv_line = invoice.line_ids.filtered(
            lambda line: line.account_type == "asset_receivable"
        )
        wizard._action_add_new_amls(inv_line, allow_partial=False)
        line = wizard.line_ids.filtered(lambda x: x.flag == "auto_balance")
        wizard._js_action_mount_line_in_edit(line.index)
        line.account_id = self.env.company.expense_currency_exchange_account_id
        wizard._line_value_changed_account_id(line)
        wizard._action_validate()

    def test_usd_statement_line_pays_mxn_invoice(self):
        date = self.frozen_today
        # 1 USD = 20 MXN
        self.setup_rates(self.usd, (date, 1 / 20.0))
        journal_usd = self.env["account.journal"].create(
            {
                "name": "Bank USD",
                "type": "bank",
                "code": "BUSD",
                "currency_id": self.usd.id,
            }
        )
        with self.mx_external_setup(date):
            # 1000 + 16% = 1160 MXN
            invoice = self._create_invoice(
                invoice_line_ids=[
                    Command.create(
                        {"product_id": self.product.id, "price_unit": 1000.0}
                    )
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            # 56 USD = 1120 MXN received; 40 MXN written off as exchange loss.
            st_line = self.env["account.bank.statement.line"].create(
                {
                    "journal_id": journal_usd.id,
                    "date": date,
                    "payment_ref": invoice.name,
                    "partner_id": self.partner_mx.id,
                    "amount": 56.0,
                }
            )
            self._reconcile_st_line_with_writeoff(st_line, invoice)
            self.assertEqual(invoice.payment_state, "paid")
            with self.with_mocked_pac_sign_success():
                st_line.move_id._l10n_mx_edi_cfdi_payment_try_send()

        document = st_line.move_id.l10n_mx_edi_payment_document_ids.filtered(
            lambda doc: doc.state == "payment_sent"
        )[:1]
        self.assertTrue(document)
        tree = etree.fromstring(document.attachment_id.raw)
        pago = tree.xpath("//pago20:Pago", namespaces=NS)[0]
        self.assertEqual(pago.get("MonedaP"), "USD")
        self.assertEqual(pago.get("Monto"), "56.00")
        self.assertEqual(pago.get("TipoCambioP"), "20.000000")
        docto = tree.xpath("//pago20:DoctoRelacionado", namespaces=NS)[0]
        self.assertEqual(docto.get("MonedaDR"), "MXN")
        self.assertEqual(docto.get("ImpPagado"), "1160.00")
        self.assertEqual(docto.get("ImpSaldoInsoluto"), "0.00")
        self.assertEqual(docto.get("EquivalenciaDR"), "20.7142857143")
        traslado_p = tree.xpath("//pago20:TrasladoP", namespaces=NS)[0]
        self.assertEqual(traslado_p.get("BaseP"), "48.275862")
        self.assertEqual(traslado_p.get("ImporteP"), "7.724138")
        totales = tree.xpath("//pago20:Totales", namespaces=NS)[0]
        self.assertEqual(totales.get("MontoTotalPagos"), "1120.00")
        self.assertEqual(totales.get("TotalTrasladosBaseIVA16"), "965.52")
        self.assertEqual(totales.get("TotalTrasladosImpuestoIVA16"), "154.48")
