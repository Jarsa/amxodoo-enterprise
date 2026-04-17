from lxml import etree

from odoo import Command
from odoo.tests import tagged

from .common import TestDecimalFixCommon


@tagged("post_install_l10n", "post_install", "-at_install")
class TestDecimalFix(TestDecimalFixCommon):
    """
    Tests for l10n_mx_edi_decimal_fix when the accounting currency has more than
    2 decimal places.

    Main case: qty=0.5, price_unit=83506.23 with MXN configured at 6 decimal places.
    The raw multiplication gives 41753.115 whose float representation may be slightly
    below the exact value.  float_round(..., precision_digits=2) would then produce
    41753.11 instead of the correct ROUND_HALF_UP result of 41753.12, causing the PAC
    to reject the CFDI due to arithmetic inconsistency.
    """

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_cfdi_tree(self, document):
        return etree.fromstring(document.attachment_id.raw)

    def _get_invoice_document(self, invoice):
        return invoice.l10n_mx_edi_invoice_document_ids.filtered(
            lambda d: d.state == "invoice_sent"
        )[:1]

    def _get_payment_document(self, payment_move):
        return payment_move.l10n_mx_edi_payment_document_ids.filtered(
            lambda d: d.state == "payment_sent"
        )[:1]

    def _assert_comprobante_amounts(self, cfdi, subtotal, total, discount=None):
        self.assertEqual(cfdi.get("SubTotal"), subtotal)
        self.assertEqual(cfdi.get("Total"), total)
        if discount is not None:
            self.assertEqual(cfdi.get("Descuento"), discount)

    def _assert_aggregate_traslado(self, cfdi, base, importe, tasa="0.160000"):
        """Assert the aggregate cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado node."""
        ns = "http://www.sat.gob.mx/cfd/4"
        traslados = cfdi.findall(
            f"{{{ns}}}Impuestos/{{{ns}}}Traslados/{{{ns}}}Traslado"
        )
        self.assertTrue(traslados, "No aggregate Traslado found in CFDI")
        traslado = traslados[0]
        self.assertEqual(traslado.get("Base"), base)
        self.assertEqual(traslado.get("Importe"), importe)
        self.assertEqual(traslado.get("TasaOCuota"), tasa)

    # -------------------------------------------------------------------------
    # Case 1: MXN 6 decimals — qty=0.5, price=83,506.23 — no discount
    # -------------------------------------------------------------------------

    def test_half_up_rounding_subtotal(self):
        """
        SubTotal = 0.5 × 83506.23 = 41753.115 → ROUND_HALF_UP to 2 dp = 41753.12.
        The bug was that float_round() rounded this to 41753.11 (HALF-EVEN or fp error),
        while format_float() via Decimal correctly gives 41753.12.
        """
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice(
                currency_id=self.mxn_currency.id,
                invoice_line_ids=[
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 0.5,
                            "price_unit": 83506.23,
                            "tax_ids": [Command.set(self.tax_16.ids)],
                        }
                    ),
                ],
            )

            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            document = self._get_invoice_document(invoice)
            self.assertTrue(document, "CFDI invoice document was not created")

            cfdi = self._get_cfdi_tree(document)
            self._assert_comprobante_amounts(
                cfdi, subtotal="41753.12", total="48433.62"
            )
            self._assert_aggregate_traslado(cfdi, base="41753.12", importe="6680.50")

    # -------------------------------------------------------------------------
    # Case 2: PPD payment after case 1 invoice
    # -------------------------------------------------------------------------

    def test_half_up_rounding_payment(self):
        """
        PPD payment for the 41753.12 + IVA invoice.
        Validates ImpSaldoAnt, ImpPagado and ImpSaldoInsoluto are coherent at 2 dp.
        """
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice(
                currency_id=self.mxn_currency.id,
                invoice_line_ids=[
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 0.5,
                            "price_unit": 83506.23,
                            "tax_ids": [Command.set(self.tax_16.ids)],
                        }
                    ),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            invoice_doc = self._get_invoice_document(invoice)
            self.assertTrue(invoice_doc)

            payment = self._create_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()

            pay_doc = self._get_payment_document(payment.move_id)
            self.assertTrue(pay_doc, "CFDI payment document was not created")

            pay_cfdi = self._get_cfdi_tree(pay_doc)
            ns_pago = "http://www.sat.gob.mx/Pagos20"

            docto_list = pay_cfdi.findall(f".//{{{ns_pago}}}DoctoRelacionado")
            self.assertTrue(docto_list, "No DoctoRelacionado in payment CFDI")
            docto = docto_list[0]
            imp_saldo_ant = docto.get("ImpSaldoAnt")
            imp_pagado = docto.get("ImpPagado")
            imp_saldo_insoluto = docto.get("ImpSaldoInsoluto")

            # After fixing the invoice CFDI, the stored invoice total is coherent
            # and the payment complement must reflect the 2-decimal rounded amount.
            self.assertEqual(imp_saldo_insoluto, "0.00")
            self.assertEqual(imp_saldo_ant, imp_pagado)

            # The paid amount must be positive and have at most 2 decimal places.
            self.assertRegex(imp_pagado, r"^\d+\.\d{2}$")

    # -------------------------------------------------------------------------
    # Case 3: USD 6 decimals — same qty/price, payment in MXN
    # -------------------------------------------------------------------------

    def test_half_up_usd_multidivisa(self):
        """
        Invoice in USD (6 decimal places) for qty=0.5, price=83506.23.
        Then a payment in MXN to validate the currency conversion path.
        """
        rate = 1.0 / 17.0  # 1 USD = 17 MXN
        self.setup_rates(self.usd_currency, (self.frozen_today, rate))

        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice(
                currency_id=self.usd_currency.id,
                invoice_line_ids=[
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 0.5,
                            "price_unit": 83506.23,
                            "tax_ids": [Command.set(self.tax_16.ids)],
                        }
                    ),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            inv_doc = self._get_invoice_document(invoice)
            self.assertTrue(
                inv_doc, "CFDI invoice document was not created for USD invoice"
            )

            inv_cfdi = self._get_cfdi_tree(inv_doc)
            self.assertEqual(inv_cfdi.get("Moneda"), "USD")
            # SubTotal must be ROUND_HALF_UP of 41753.115 to 2 dp = 41753.12
            self._assert_comprobante_amounts(
                inv_cfdi, subtotal="41753.12", total="48433.62"
            )

        with self.mx_external_setup(self.frozen_today):
            payment = self._create_payment(
                invoice,
                currency_id=self.mxn_currency.id,
            )
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()

            pay_doc = self._get_payment_document(payment.move_id)
            self.assertTrue(
                pay_doc, "CFDI payment document was not created for USD→MXN"
            )

    # -------------------------------------------------------------------------
    # Case 4: MXN 6 decimals — same qty/price with 10% discount
    # -------------------------------------------------------------------------

    def test_half_up_rounding_with_discount(self):
        """
        10% discount on same line.
        SubTotal (gross) = 41753.12, Descuento = 4175.31 (ROUND_HALF_UP of 4175.3115).
        Validates that the Descuento attribute is correctly included and Total is
        coherent.
        """
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice(
                currency_id=self.mxn_currency.id,
                invoice_line_ids=[
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 0.5,
                            "price_unit": 83506.23,
                            "discount": 10.0,
                            "tax_ids": [Command.set(self.tax_16.ids)],
                        }
                    ),
                ],
            )
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            document = self._get_invoice_document(invoice)
            self.assertTrue(document)

            cfdi = self._get_cfdi_tree(document)
            # SubTotal is gross (before discount) = ROUND_HALF_UP(41753.115) = 41753.12
            self.assertEqual(cfdi.get("SubTotal"), "41753.12")
            # Descuento = ROUND_HALF_UP(4175.3115) = 4175.31
            self.assertEqual(cfdi.get("Descuento"), "4175.31")
            # Total must be a valid 2-decimal number
            self.assertRegex(cfdi.get("Total"), r"^\d+\.\d{2}$")
            # Total = SubTotal - Descuento + IVA → must be positive
            total = float(cfdi.get("Total"))
            self.assertGreater(total, 0.0)
