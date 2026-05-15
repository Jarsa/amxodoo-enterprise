from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import TestCfdiPaymentFollowupCommon


@tagged("post_install", "-at_install")
class TestXmlValidation(TestCfdiPaymentFollowupCommon):
    def setUp(self):
        super().setUp()
        # Reset payment move state before each test
        self.payment.move_id.write(
            {
                "l10n_mx_edi_cfdi_uuid": False,
                "l10n_mx_edi_cfdi_payment_state": "pending",
            }
        )
        self.payment_uuid = "PAY-UUID-0000-0000-TEST-0001"

    def test_valid_xml_sets_validated(self):
        """All validations pass → state 'validated', UUID stored."""
        xml = self._build_cfdi_xml(
            payment_uuid=self.payment_uuid,
            payment_date=fields.Date.today(),
            amount=5000.0,
            invoice_uuids=[self.invoice_uuid],
        )
        self._attach_xml(self.payment.move_id, xml)
        self.assertEqual(
            self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "validated"
        )
        self.assertEqual(self.payment.move_id.l10n_mx_edi_cfdi_uuid, self.payment_uuid)

    def test_non_payment_xml_skipped(self):
        """TipoDeComprobante='I' (invoice XML) → no state change."""
        from lxml import etree

        CFDI = "http://www.sat.gob.mx/cfd/4"
        root = etree.Element("{%s}Comprobante" % CFDI)
        root.set("TipoDeComprobante", "I")
        xml_bytes = etree.tostring(root, xml_declaration=True, encoding="UTF-8")

        self._attach_xml(self.payment.move_id, xml_bytes)
        # State must remain unchanged (pending from setUp)
        self.assertEqual(self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "pending")

    def test_non_xml_attachment_ignored(self):
        """PDF attachment → no processing, state unchanged."""
        attachment = self.env["ir.attachment"].create(
            {
                "name": "document.pdf",
                "raw": b"fake pdf content",
                "res_model": "account.move",
                "res_id": self.payment.move_id.id,
                "mimetype": "application/pdf",
            }
        )
        self.payment.move_id._process_cfdi_payment_xml(attachment)
        self.assertEqual(self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "pending")

    def test_invalid_forma_pago(self):
        """FormaDePagoP != '03' → state 'error', message contains 'SPEI'."""
        xml = self._build_cfdi_xml(
            payment_uuid=self.payment_uuid,
            payment_date=fields.Date.today(),
            amount=5000.0,
            invoice_uuids=[self.invoice_uuid],
            forma_pago="01",
        )
        self._attach_xml(self.payment.move_id, xml)
        self.assertEqual(self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "error")
        # Check activity was created
        activities = self.payment.move_id.activity_ids
        self.assertTrue(activities)
        self.assertIn("SPEI", activities[0].note or "")

    def test_date_before_payment(self):
        """FechaPago one day before payment date → state 'error'."""
        yesterday = fields.Date.today() - timedelta(days=1)
        xml = self._build_cfdi_xml(
            payment_uuid=self.payment_uuid,
            payment_date=yesterday,
            amount=5000.0,
            invoice_uuids=[self.invoice_uuid],
        )
        self._attach_xml(self.payment.move_id, xml)
        self.assertEqual(self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "error")

    def test_date_within_tolerance(self):
        """FechaPago 2 days after payment date → validated (default tolerance=2)."""
        self.env["ir.config_parameter"].set_param(
            "l10n_mx_edi_cfdi_payment_date_tolerance_days", "2"
        )
        two_days_later = fields.Date.today() + timedelta(days=2)
        xml = self._build_cfdi_xml(
            payment_uuid=self.payment_uuid,
            payment_date=two_days_later,
            amount=5000.0,
            invoice_uuids=[self.invoice_uuid],
        )
        self._attach_xml(self.payment.move_id, xml)
        self.assertEqual(
            self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "validated"
        )

    def test_date_exceeds_tolerance(self):
        """FechaPago 3 days after payment when tolerance=2 → 'error'."""
        self.env["ir.config_parameter"].set_param(
            "l10n_mx_edi_cfdi_payment_date_tolerance_days", "2"
        )
        three_days_later = fields.Date.today() + timedelta(days=3)
        xml = self._build_cfdi_xml(
            payment_uuid=self.payment_uuid,
            payment_date=three_days_later,
            amount=5000.0,
            invoice_uuids=[self.invoice_uuid],
        )
        self._attach_xml(self.payment.move_id, xml)
        self.assertEqual(self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "error")

    def test_uuid_not_in_reconciled(self):
        """IdDocumento UUID not in reconciled invoices → 'error'."""
        xml = self._build_cfdi_xml(
            payment_uuid=self.payment_uuid,
            payment_date=fields.Date.today(),
            amount=5000.0,
            invoice_uuids=["UNKNOWN-UUID-NOT-RECONCILED"],
        )
        self._attach_xml(self.payment.move_id, xml)
        self.assertEqual(self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "error")

    def test_saldo_insoluto_nonzero(self):
        """ImporteSaldoInsoluto != '0.00' → 'error'."""
        xml = self._build_cfdi_xml(
            payment_uuid=self.payment_uuid,
            payment_date=fields.Date.today(),
            amount=5000.0,
            invoice_uuids=[self.invoice_uuid],
            saldo_insoluto="150.00",
        )
        self._attach_xml(self.payment.move_id, xml)
        self.assertEqual(self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "error")

    def test_amount_mismatch(self):
        """Monto differs by 5.00 from Odoo amount → 'error'."""
        xml = self._build_cfdi_xml(
            payment_uuid=self.payment_uuid,
            payment_date=fields.Date.today(),
            amount=4995.0,  # 5000 - 5 > tolerance of 1
            invoice_uuids=[self.invoice_uuid],
        )
        self._attach_xml(self.payment.move_id, xml)
        self.assertEqual(self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "error")

    def test_amount_within_tolerance(self):
        """Monto differs by 0.50 (within ±1.00 tolerance) → 'validated'."""
        xml = self._build_cfdi_xml(
            payment_uuid=self.payment_uuid,
            payment_date=fields.Date.today(),
            amount=5000.50,
            invoice_uuids=[self.invoice_uuid],
        )
        self._attach_xml(self.payment.move_id, xml)
        self.assertEqual(
            self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "validated"
        )

    def test_multiple_errors_reported(self):
        """Multiple failures (forma_pago + unknown uuid + nonzero saldo) → one error."""
        xml = self._build_cfdi_xml(
            payment_uuid=self.payment_uuid,
            payment_date=fields.Date.today(),
            amount=5000.0,
            invoice_uuids=["UNKNOWN-UUID"],
            forma_pago="01",
            saldo_insoluto="100.00",
        )
        self._attach_xml(self.payment.move_id, xml)
        self.assertEqual(self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "error")
        # Activity note should contain all 3 error messages
        activities = self.payment.move_id.activity_ids
        self.assertTrue(activities)
        note = activities[0].note or ""
        self.assertIn("SPEI", note)
        self.assertIn("UNKNOWN-UUID", note)
        self.assertIn("100.00", note)

    def test_idempotent_same_uuid(self):
        """Reattaching the same UUID → no reprocessing, state unchanged."""
        # First: validate
        xml = self._build_cfdi_xml(
            payment_uuid=self.payment_uuid,
            payment_date=fields.Date.today(),
            amount=5000.0,
            invoice_uuids=[self.invoice_uuid],
        )
        self._attach_xml(self.payment.move_id, xml)
        self.assertEqual(
            self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "validated"
        )
        # Remove activities to detect new ones
        self.payment.move_id.activity_ids.unlink()
        # Second: same XML again
        self._attach_xml(self.payment.move_id, xml, filename="complement2.xml")
        # State must remain validated, no new activity
        self.assertEqual(
            self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "validated"
        )
        self.assertFalse(self.payment.move_id.activity_ids)

    def test_validation_success_closes_error_activities(self):
        """Successful XML validation closes any prior CFDI error activities."""
        move = self.payment.move_id
        summary = move._get_cfdi_error_activity_summary()

        # First: invalid XML → error state + activity
        bad_xml = self._build_cfdi_xml(
            payment_uuid=self.payment_uuid,
            payment_date=fields.Date.today(),
            amount=5000.0,
            invoice_uuids=[self.invoice_uuid],
            forma_pago="01",
        )
        self._attach_xml(move, bad_xml, filename="bad.xml")
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "error")
        self.assertTrue(
            move.activity_ids.filtered(lambda a: a.summary == summary),
            "Expected an error activity after invalid XML",
        )

        # Reset UUID so the new XML is treated as a fresh validation
        move.write({"l10n_mx_edi_cfdi_uuid": False})

        # Second: valid XML → validated, error activity should be closed
        good_xml = self._build_cfdi_xml(
            payment_uuid="PAY-UUID-0000-0000-TEST-9999",
            payment_date=fields.Date.today(),
            amount=5000.0,
            invoice_uuids=[self.invoice_uuid],
        )
        self._attach_xml(move, good_xml, filename="good.xml")
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "validated")
        self.assertFalse(
            move.activity_ids.filtered(lambda a: a.summary == summary),
            "Error activity should have been closed after successful validation",
        )

    def test_configurable_date_tolerance(self):
        """Override tolerance to 0 days: date same as payment is ok, +1 day is error."""
        self.env["ir.config_parameter"].set_param(
            "l10n_mx_edi_cfdi_payment_date_tolerance_days", "0"
        )
        # Same day → validated
        xml_same = self._build_cfdi_xml(
            payment_uuid=self.payment_uuid,
            payment_date=fields.Date.today(),
            amount=5000.0,
            invoice_uuids=[self.invoice_uuid],
        )
        self._attach_xml(self.payment.move_id, xml_same)
        self.assertEqual(
            self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "validated"
        )
        # Reset
        self.payment.move_id.write(
            {
                "l10n_mx_edi_cfdi_uuid": False,
                "l10n_mx_edi_cfdi_payment_state": "pending",
            }
        )
        # +1 day → error
        tomorrow = fields.Date.today() + timedelta(days=1)
        xml_late = self._build_cfdi_xml(
            payment_uuid="PAY-UUID-0000-0000-TEST-0002",
            payment_date=tomorrow,
            amount=5000.0,
            invoice_uuids=[self.invoice_uuid],
        )
        self._attach_xml(self.payment.move_id, xml_late)
        self.assertEqual(self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "error")
