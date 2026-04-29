from decimal import Decimal

from lxml import etree

from odoo import Command
from odoo.tests import tagged
from odoo.tools.float_utils import float_round

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
        SubTotal (gross) = 41753.12, Descuento = 4175.31 (HALF-UP of 4175.3115).
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

    # -------------------------------------------------------------------------
    # Case 6: Multi-line USD invoice where sum(Concepto.Importe) has 3+ decimal
    # places, causing SubTotal != round(sum, 2) without the fix.
    # Reproduces real CFDI FCC-C06574 (24 lines, sum=22966.725, USD 6dp).
    # SAT error: "El campo SubTotal no es igual al redondeo de la suma de los
    # importes de los conceptos registrados" for TipoDeComprobante I, E y T.
    # -------------------------------------------------------------------------

    # Lines extracted from FCC-C06574-MX-Invoice-4.0.xml
    # sum(qty * price) = 22966.725000 → ROUND_UP/ROUND_HALF_UP at 2dp = 22966.73
    # Without the fix, float arithmetic may yield 22966.72 (banker's rounding /
    # float underrepresentation of the .725 boundary).
    _FCC_C06574_LINES = [
        (3.9, 279.28),  # PUR6004BU-FE:              1089.192
        (0.9, 430.87),  # PUO6C04BL-CEG:              387.783
        (0.3, 176.84),  # SP688-C:                     53.052
        (16.8, 12.63),  # CJ688TGBU:                  212.184
        (8.4, 10.33),  # UTP28SP8INBU:                86.772
        (5.1, 13.71),  # UTP28SP7BU:                  69.921
        (0.3, 131.58),  # Miscellaneous:               39.474
        (0.3, 8914.29),  # SP Cont Infrastructure:   2674.287
        (2.7, 848.25),  # M4318-PLVE:                2290.275
        (2.7, 47.13),  # T94K01D:                    127.251
        (0.3, 106.44),  # 01473-001:                   31.932
        (1.5, 177.94),  # T91B53:                     266.910
        (4.2, 285.19),  # T8129-E:                   1197.798
        (3.3, 803.56),  # P1467-LE:                  2651.748
        (2.7, 94.25),  # T91B47:                     254.475
        (1.2, 455.00),  # AXIS M4216-LV:              546.000
        (124.5, 22.38),  # MT TBPD75:                 2786.310
        (18.0, 28.06),  # MTTBPG75:                   505.080
        (30.0, 168.83),  # SP Cont Infrastructure:   5064.900
        (0.6, 771.80),  # MT REG60X60:                463.080
        (1.2, 240.65),  # KLP-DIPOLO-BASIC:           288.780
        (0.3, 1929.50),  # 8095:                       578.850
        (13.5, 62.71),  # SP Cont Security:           846.585
        (0.3, 1513.62),  # MT RENTA DE PLATAFORMA:     454.086
    ]

    def _assert_subtotal_equals_sum_of_conceptos(self, cfdi, rounding_method):
        """
        Validates the SAT rule: SubTotal == round(sum(Concepto.Importe), 2).

        Uses float_round with HALF-UP (module's method) to compute expected
        SubTotal from the individual Concepto.Importe values already in the CFDI.
        """
        ns = "http://www.sat.gob.mx/cfd/4"
        conceptos = cfdi.findall(f"{{{ns}}}Conceptos/{{{ns}}}Concepto")
        self.assertTrue(conceptos, f"No Conceptos in CFDI ({rounding_method})")

        subtotal_str = cfdi.get("SubTotal")
        self.assertRegex(
            subtotal_str,
            r"^\d+\.\d{2}$",
            f"SubTotal must have exactly 2 decimal places ({rounding_method})",
        )

        sum_importes = sum(float(c.get("Importe", "0")) for c in conceptos)
        expected = float_round(
            sum_importes, precision_digits=2, rounding_method="HALF-UP"
        )
        self.assertEqual(
            float(subtotal_str),
            expected,
            f"SubTotal ({subtotal_str}) != rounded sum of importes "
            f"({sum_importes:.6f} → {expected:.2f}) ({rounding_method})",
        )

        total_str = cfdi.get("Total")
        self.assertRegex(
            total_str,
            r"^\d+\.\d{2}$",
            f"Total must have exactly 2 decimal places ({rounding_method})",
        )

    def test_subtotal_multiline_sum_consistency_ingreso(self):
        """
        TipoDeComprobante I: 24 USD lines where sum(Importe) = 22966.725.

        Without the fix, float arithmetic may yield SubTotal = 22966.72
        (banker's rounding / float underrepresentation of .725), triggering
        the SAT error "El campo SubTotal no es igual al redondeo de la suma de los
        importes de los conceptos registrados".

        With the fix, SubTotal = 22966.73 (HALF-UP of the internal value).
        """
        rate = 1.0 / 17.3323
        self.setup_rates(self.usd_currency, (self.frozen_today, rate))

        def run(rounding_method):
            with self.mx_external_setup(self.frozen_today):
                invoice = self._create_invoice(
                    currency_id=self.usd_currency.id,
                    invoice_line_ids=[
                        Command.create(
                            {
                                "product_id": self.product.id,
                                "quantity": qty,
                                "price_unit": price,
                                "tax_ids": [Command.set(self.tax_16.ids)],
                            }
                        )
                        for qty, price in self._FCC_C06574_LINES
                    ],
                )
                with self.with_mocked_pac_sign_success():
                    invoice._l10n_mx_edi_cfdi_invoice_try_send()

                document = self._get_invoice_document(invoice)
                self.assertTrue(
                    document,
                    f"CFDI not generated for TipoDeComprobante I ({rounding_method})",
                )

                cfdi = self._get_cfdi_tree(document)
                self.assertEqual(
                    cfdi.get("TipoDeComprobante"),
                    "I",
                    f"Expected TipoDeComprobante=I ({rounding_method})",
                )
                self.assertEqual(
                    len(
                        cfdi.findall(
                            "{http://www.sat.gob.mx/cfd/4}Conceptos"
                            "/{http://www.sat.gob.mx/cfd/4}Concepto"
                        )
                    ),
                    len(self._FCC_C06574_LINES),
                )
                self._assert_subtotal_equals_sum_of_conceptos(cfdi, rounding_method)

        self._test_cfdi_rounding(run)

    def test_subtotal_multiline_sum_consistency_egreso(self):
        """
        TipoDeComprobante E: credit note with the same 24 USD lines.

        Verifies that the SAT rule (SubTotal == round(sum(Importe), 2)) also
        holds for expense vouchers, where the module applies the same HALF-UP
        rounding via format_float.
        """
        rate = 1.0 / 17.3323
        self.setup_rates(self.usd_currency, (self.frozen_today, rate))

        def run(rounding_method):
            with self.mx_external_setup(self.frozen_today):
                invoice = self._create_invoice(
                    move_type="out_refund",
                    currency_id=self.usd_currency.id,
                    invoice_line_ids=[
                        Command.create(
                            {
                                "product_id": self.product.id,
                                "quantity": qty,
                                "price_unit": price,
                                "tax_ids": [Command.set(self.tax_16.ids)],
                            }
                        )
                        for qty, price in self._FCC_C06574_LINES
                    ],
                )
                with self.with_mocked_pac_sign_success():
                    invoice._l10n_mx_edi_cfdi_invoice_try_send()

                document = self._get_invoice_document(invoice)
                self.assertTrue(
                    document,
                    f"CFDI not generated for TipoDeComprobante E ({rounding_method})",
                )

                cfdi = self._get_cfdi_tree(document)
                self.assertEqual(
                    cfdi.get("TipoDeComprobante"),
                    "E",
                    f"Expected TipoDeComprobante=E ({rounding_method})",
                )
                self._assert_subtotal_equals_sum_of_conceptos(cfdi, rounding_method)

        self._test_cfdi_rounding(run)

    # -------------------------------------------------------------------------
    # Helpers for Total arithmetic consistency
    # -------------------------------------------------------------------------

    def _assert_total_arithmetic_consistency(
        self, cfdi, subtotal, total_impuestos, total, rounding_method
    ):
        """
        Validates:
          - SubTotal, TotalImpuestosTrasladados and Total have exactly 2dp
          - Total == SubTotal + TotalImpuestosTrasladados (not from the raw sum)
        """
        ns = "http://www.sat.gob.mx/cfd/4"

        self.assertEqual(
            cfdi.get("SubTotal"), subtotal,
            f"Incorrect SubTotal ({rounding_method})"
        )
        self.assertEqual(
            cfdi.get("Total"), total,
            f"Incorrect Total ({rounding_method})"
        )

        impuestos = cfdi.find(f"{{{ns}}}Impuestos")
        actual = impuestos.get("TotalImpuestosTrasladados") if impuestos is not None else None
        self.assertEqual(
            actual, total_impuestos,
            f"Incorrect TotalImpuestosTrasladados ({rounding_method})"
        )

        expected_total = round(float(subtotal) + float(total_impuestos), 2)
        self.assertAlmostEqual(
            float(total), expected_total, places=2,
            msg=(
                f"Total arithmetically inconsistent: "
                f"{subtotal} + {total_impuestos} = {expected_total:.2f} ≠ {total} "
                f"({rounding_method})"
            ),
        )

    # -------------------------------------------------------------------------
    # Case 7: FCJ-A08414 — MXN 6dp, 3 lines
    # SubTotal=8258.60, TotalImpuestos=1321.38, Total=9579.98
    # -------------------------------------------------------------------------

    _FCJ_A08414_LINES = [
        (1.0, 5957.70),   # Office network node max height 3m:  5957.70
        (7.0,  135.90),   # Infrastructure supply conduit:       951.30
        (1.0, 1349.60),   # Professional services:              1349.60
    ]

    def test_total_arithmetic_consistency_mxn_3lines(self):
        """
        FCJ-A08414: 3 MXN lines. sum(IVA raw) = 1321.376 → HALF-UP → 1321.38.
        Total = 8258.60 + 1321.38 = 9579.98.

        Validates that Total is computed from already-rounded values,
        not from raw floats.
        """

        def run(rounding_method):
            with self.mx_external_setup(self.frozen_today):
                invoice = self._create_invoice(
                    currency_id=self.mxn_currency.id,
                    invoice_line_ids=[
                        Command.create(
                            {
                                "product_id": self.product.id,
                                "quantity": qty,
                                "price_unit": price,
                                "tax_ids": [Command.set(self.tax_16.ids)],
                            }
                        )
                        for qty, price in self._FCJ_A08414_LINES
                    ],
                )
                with self.with_mocked_pac_sign_success():
                    invoice._l10n_mx_edi_cfdi_invoice_try_send()

                document = self._get_invoice_document(invoice)
                self.assertTrue(
                    document,
                    f"CFDI not generated for FCJ-A08414 ({rounding_method})",
                )
                cfdi = self._get_cfdi_tree(document)
                self._assert_total_arithmetic_consistency(
                    cfdi,
                    subtotal="8258.60",
                    total_impuestos="1321.38",
                    total="9579.98",
                    rounding_method=rounding_method,
                )

        self._test_cfdi_rounding(run)

    # -------------------------------------------------------------------------
    # Case 8: FCJ-A08415 — MXN 6dp, 19 lines, sum(IVA)=13874.512 → 13874.51
    # SubTotal=86715.70, TotalImpuestos=13874.51, Total=100590.21
    # -------------------------------------------------------------------------

    _FCJ_A08415_LINES = [
        (7.0,  3702.88),   # Category 6 plenum cable:            25920.16
        (7.0,   251.30),   # RJ45 Cat6 jack:                      1759.10
        (7.0,    46.30),   # Face plate 2/4 ports:                  324.10
        (7.0,   247.45),   # Patch cord 5FT:                      1732.15
        (7.0,   299.39),   # Patch cord 7FT:                      2095.73
        (7.0,    33.58),   # Labeled face plate & patch panel:      235.06
        (7.0,    33.58),   # Labeled both sides cable:              235.06
        (7.0,    33.58),   # Labeled patchcords:                    235.06
        (7.0,    44.65),   # Wiring management:                     312.55
        (7.0,   111.00),   # Scanner test:                          777.00
        (7.0,    44.44),   # Updates:                               311.08
        (7.0,    66.65),   # FS box:                                466.55
        (7.0,   177.74),   # Operational costs:                   1244.18
        (7.0,  2558.56),   # Network node max height 9m:         17909.92
        (1.0,  2295.00),   # Single node relocation:              2295.00
        (35.0,  165.00),   # Flexible conduit 3/4":               5775.00
        (24.0,  331.00),   # Flexible conduit 2":                 7944.00
        (1.0, 10335.00),   # Infrastructure implementation:      10335.00
        (1.0,  6809.00),   # Professional services:               6809.00
    ]

    def test_total_arithmetic_consistency_mxn_19lines(self):
        """
        FCJ-A08415: 19 MXN lines. sum(IVA raw) = 13874.512 → HALF-UP → 13874.51.
        Total = 86715.70 + 13874.51 = 100590.21.

        Validates that Total is computed by summing already-rounded values,
        not from raw floats.
        """

        def run(rounding_method):
            with self.mx_external_setup(self.frozen_today):
                invoice = self._create_invoice(
                    currency_id=self.mxn_currency.id,
                    invoice_line_ids=[
                        Command.create(
                            {
                                "product_id": self.product.id,
                                "quantity": qty,
                                "price_unit": price,
                                "tax_ids": [Command.set(self.tax_16.ids)],
                            }
                        )
                        for qty, price in self._FCJ_A08415_LINES
                    ],
                )
                with self.with_mocked_pac_sign_success():
                    invoice._l10n_mx_edi_cfdi_invoice_try_send()

                document = self._get_invoice_document(invoice)
                self.assertTrue(
                    document,
                    f"CFDI not generated for FCJ-A08415 ({rounding_method})",
                )
                cfdi = self._get_cfdi_tree(document)
                self.assertEqual(
                    len(cfdi.findall(
                        "{http://www.sat.gob.mx/cfd/4}Conceptos"
                        "/{http://www.sat.gob.mx/cfd/4}Concepto"
                    )),
                    len(self._FCJ_A08415_LINES),
                )
                self._assert_total_arithmetic_consistency(
                    cfdi,
                    subtotal="86715.70",
                    total_impuestos="13874.51",
                    total="100590.21",
                    rounding_method=rounding_method,
                )

        self._test_cfdi_rounding(run)

    # -------------------------------------------------------------------------
    # Case 9: FCG-G10028403 — USD 6dp, 4 lines, TipoCambio=18.439991
    # SubTotal=7150.10, TotalImpuestos=1144.02, Total=8294.12
    # -------------------------------------------------------------------------

    _FCG_G10028403_LINES = [
        (1.0, 5074.09),   # SP IFI Security cameras:    5074.09
        (1.0,  948.53),   # Genetec update:               948.53
        (1.0, 1064.98),   # Security Center license:     1064.98
        (1.0,   62.50),   # Genetec SDK connection:        62.50
    ]

    def test_total_arithmetic_consistency_usd_tipocambio(self):
        """
        FCG-G10028403: 4 USD lines with TipoCambio=18.439991, MetodoPago=PPD.
        sum(Importe) = 7150.10, sum(IVA raw) = 1144.016 → HALF-UP → 1144.02.
        Total = 7150.10 + 1144.02 = 8294.12.

        Validates arithmetic consistency of the CFDI in foreign currency.
        """
        rate = 1.0 / 18.439991
        self.setup_rates(self.usd_currency, (self.frozen_today, rate))

        def run(rounding_method):
            with self.mx_external_setup(self.frozen_today):
                invoice = self._create_invoice(
                    currency_id=self.usd_currency.id,
                    invoice_line_ids=[
                        Command.create(
                            {
                                "product_id": self.product.id,
                                "quantity": qty,
                                "price_unit": price,
                                "tax_ids": [Command.set(self.tax_16.ids)],
                            }
                        )
                        for qty, price in self._FCG_G10028403_LINES
                    ],
                )
                with self.with_mocked_pac_sign_success():
                    invoice._l10n_mx_edi_cfdi_invoice_try_send()

                document = self._get_invoice_document(invoice)
                self.assertTrue(
                    document,
                    f"CFDI not generated for FCG-G10028403 ({rounding_method})",
                )
                cfdi = self._get_cfdi_tree(document)
                self.assertEqual(cfdi.get("Moneda"), "USD")
                self._assert_total_arithmetic_consistency(
                    cfdi,
                    subtotal="7150.10",
                    total_impuestos="1144.02",
                    total="8294.12",
                    rounding_method=rounding_method,
                )

        self._test_cfdi_rounding(run)
