from decimal import Decimal

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

    With round_globally, _get_post_fix_tax_amounts_map uses float_round to compute
    new_base_amount, which can shift the base by ±1 unit at 6dp (e.g. 41753.115 →
    41753.114).  That delta propagates to cfdi_line_values['importe'] and then to
    cfdi_values['subtotal'], breaking the 2dp rounding.  The fix overrides
    _get_post_fix_tax_amounts_map to use Decimal ROUND_HALF_UP throughout.
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
    # Both round_per_line and round_globally must produce identical CFDI amounts.
    # -------------------------------------------------------------------------

    def test_half_up_rounding_subtotal(self):
        """
        SubTotal = 0.5 × 83506.23 = 41753.115 → ROUND_HALF_UP to 2 dp = 41753.12.
        Tested for both round_per_line and round_globally.
        """

        def run(rounding_method):
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
                self.assertTrue(
                    document,
                    f"CFDI invoice document not created ({rounding_method})",
                )

                cfdi = self._get_cfdi_tree(document)
                self._assert_comprobante_amounts(
                    cfdi, subtotal="41753.12", total="48433.62"
                )
                self._assert_aggregate_traslado(
                    cfdi, base="41753.12", importe="6680.50"
                )

        self._test_cfdi_rounding(run)

    # -------------------------------------------------------------------------
    # Case 2: PPD payment after case 1 invoice — both rounding methods
    # -------------------------------------------------------------------------

    def test_half_up_rounding_payment(self):
        """
        PPD payment for the 41753.12 + IVA invoice.
        Validates ImpSaldoAnt, ImpPagado and ImpSaldoInsoluto are coherent at 2 dp.
        Tested for both round_per_line and round_globally.
        """

        def run(rounding_method):
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
                self.assertTrue(
                    pay_doc,
                    f"CFDI payment document not created ({rounding_method})",
                )

                pay_cfdi = self._get_cfdi_tree(pay_doc)
                ns_pago = "http://www.sat.gob.mx/Pagos20"

                docto_list = pay_cfdi.findall(f".//{{{ns_pago}}}DoctoRelacionado")
                self.assertTrue(docto_list, "No DoctoRelacionado in payment CFDI")
                docto = docto_list[0]
                imp_saldo_ant = docto.get("ImpSaldoAnt")
                imp_pagado = docto.get("ImpPagado")
                imp_saldo_insoluto = docto.get("ImpSaldoInsoluto")

                self.assertEqual(imp_saldo_insoluto, "0.00")
                self.assertEqual(imp_saldo_ant, imp_pagado)
                self.assertRegex(imp_pagado, r"^\d+\.\d{2}$")

        self._test_cfdi_rounding(run)

    # -------------------------------------------------------------------------
    # Case 3: USD 6 decimals — same qty/price, payment in MXN — both methods
    # -------------------------------------------------------------------------

    def test_half_up_usd_multidivisa(self):
        """
        Invoice in USD (6 decimal places) for qty=0.5, price=83506.23.
        Then a payment in MXN to validate the currency conversion path.
        Tested for both round_per_line and round_globally.
        """
        rate = 1.0 / 17.0  # 1 USD = 17 MXN
        self.setup_rates(self.usd_currency, (self.frozen_today, rate))

        def run(rounding_method):
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
                    inv_doc,
                    f"CFDI invoice document not created for USD ({rounding_method})",
                )

                inv_cfdi = self._get_cfdi_tree(inv_doc)
                self.assertEqual(inv_cfdi.get("Moneda"), "USD")
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
                    pay_doc,
                    f"CFDI payment document not created for USD→MXN ({rounding_method})",
                )

        self._test_cfdi_rounding(run)

    # -------------------------------------------------------------------------
    # Case 4: MXN 6 decimals — same qty/price with 10% discount — both methods
    # -------------------------------------------------------------------------

    def test_half_up_rounding_with_discount(self):
        """
        10% discount on same line.
        SubTotal (gross) = 41753.12, Descuento = 4175.31 (ROUND_HALF_UP of 4175.3115).
        Tested for both round_per_line and round_globally.
        """

        def run(_rounding_method):
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
                self.assertEqual(cfdi.get("SubTotal"), "41753.12")
                self.assertEqual(cfdi.get("Descuento"), "4175.31")
                self.assertRegex(cfdi.get("Total"), r"^\d+\.\d{2}$")
                total = float(cfdi.get("Total"))
                self.assertGreater(total, 0.0)

        self._test_cfdi_rounding(run)

    # -------------------------------------------------------------------------
    # Case 5: BaseDR / BaseP consistency at 6dp — SAT validation rule
    # -------------------------------------------------------------------------

    def test_traslado_dr_base_p_consistency(self):
        """
        USD invoice with a price that yields a base with more than 2 decimal
        places when stored with 6dp precision (e.g. 500.001).

        Root cause: the original payment20 template formats BaseDR to 2dp while
        BaseP already uses 6dp.  With 6dp accounting the values can diverge:
          BaseDR = "500.00"  (2dp)
          BaseP  = "500.001000"  (6dp)
        SAT rejects with:
          "El campo BaseP... no es igual a la suma de los importes de las bases
           registrados en los documentos relacionados..."

        Fix: TrasladoDR is overridden to use 6dp so both sides match exactly.
        Tested for both round_per_line and round_globally.
        """
        rate = 1.0 / 17.0
        self.setup_rates(self.usd_currency, (self.frozen_today, rate))

        def run(rounding_method):
            with self.mx_external_setup(self.frozen_today):
                invoice = self._create_invoice(
                    currency_id=self.usd_currency.id,
                    invoice_line_ids=[
                        Command.create(
                            {
                                "product_id": self.product.id,
                                "quantity": 1,
                                "price_unit": 500.001,
                                "tax_ids": [Command.set(self.tax_16.ids)],
                            }
                        ),
                    ],
                )
                with self.with_mocked_pac_sign_success():
                    invoice._l10n_mx_edi_cfdi_invoice_try_send()

                payment = self._create_payment(
                    invoice, currency_id=self.usd_currency.id
                )
                with self.with_mocked_pac_sign_success():
                    payment.move_id._l10n_mx_edi_cfdi_payment_try_send()

                pay_doc = self._get_payment_document(payment.move_id)
                self.assertTrue(
                    pay_doc,
                    f"No payment document created ({rounding_method})",
                )

                pay_cfdi = self._get_cfdi_tree(pay_doc)
                ns_pago = "http://www.sat.gob.mx/Pagos20"

                # Collect BaseDR values per DoctoRelacionado and verify 6dp.
                docto_list = pay_cfdi.findall(f".//{{{ns_pago}}}DoctoRelacionado")
                self.assertTrue(
                    docto_list, f"No DoctoRelacionado found ({rounding_method})"
                )
                base_dr_total = Decimal("0")
                for docto in docto_list:
                    equivalencia = Decimal(docto.get("EquivalenciaDR") or "1")
                    traslados_dr = docto.findall(
                        f"{{{ns_pago}}}ImpuestosDR"
                        f"/{{{ns_pago}}}TrasladosDR"
                        f"/{{{ns_pago}}}TrasladoDR"
                    )
                    for tdr in traslados_dr:
                        base_dr_str = tdr.get("BaseDR", "0")
                        self.assertRegex(
                            base_dr_str,
                            r"^\d+\.\d{6}$",
                            f"BaseDR must have 6 decimal places ({rounding_method})",
                        )
                        base_dr_total += Decimal(base_dr_str) / equivalencia

                # BaseP must equal sum(BaseDR / EquivalenciaDR) exactly at 6dp.
                traslados_p = pay_cfdi.findall(f".//{{{ns_pago}}}TrasladoP")
                self.assertTrue(traslados_p, f"No TrasladoP found ({rounding_method})")
                for tp in traslados_p:
                    base_p_str = tp.get("BaseP", "0")
                    self.assertRegex(
                        base_p_str,
                        r"^\d+\.\d{6}$",
                        f"BaseP must have 6 decimal places ({rounding_method})",
                    )
                    self.assertEqual(
                        Decimal(base_p_str),
                        base_dr_total,
                        f"BaseP must equal sum(BaseDR/EquivalenciaDR) ({rounding_method})",
                    )

        self._test_cfdi_rounding(run)
