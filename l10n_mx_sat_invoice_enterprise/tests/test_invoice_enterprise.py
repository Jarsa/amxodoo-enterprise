# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.l10n_mx_sat_invoice.tests.test_invoice_wizard import (
    TestInvoiceWizard,
)

_FETCH = (
    "odoo.addons.l10n_mx_edi.models.l10n_mx_edi_document."
    "L10n_Mx_EdiDocument._fetch_sat_status"
)


@tagged("post_install", "-at_install")
class TestInvoiceEnterprise(TestInvoiceWizard):
    """Re-run the base tests with l10n_mx_edi and add the Enterprise checks."""

    allow_inherited_tests_method = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.startClassPatcher(patch(_FETCH, return_value={"value": "valid"}))

    def test_received_edi_document(self):
        document = self._create_document()
        move = self.env["account.move"].browse(
            self._create_invoices(document)[1]["res_id"]
        )
        self.assertRecordValues(
            move,
            [
                {
                    "l10n_mx_edi_cfdi_uuid": document.uuid,
                    "l10n_mx_edi_cfdi_state": "received",
                    "l10n_mx_edi_cfdi_sat_state": "valid",
                    "l10n_mx_edi_payment_policy": "PUE",
                    "l10n_mx_edi_usage": "G03",
                }
            ],
        )
        self.assertEqual(move.l10n_mx_edi_payment_method_id.code, "03")
        self.assertEqual(move.l10n_mx_edi_document_ids.state, "invoice_received")
        self.assertEqual(document.sat_status, "valid")

    def test_issued_edi_document(self):
        document = self._create_document(direction="issued")
        move = self.env["account.move"].browse(
            self._create_invoices(document)[1]["res_id"]
        )
        self.assertRecordValues(
            move,
            [
                {
                    "l10n_mx_edi_cfdi_uuid": document.uuid,
                    "l10n_mx_edi_cfdi_state": "sent",
                }
            ],
        )
        self.assertEqual(move.l10n_mx_edi_document_ids.state, "invoice_sent")

    def test_refund_origin(self):
        related = (
            '<cfdi:CfdiRelacionados TipoRelacion="01">'
            '<cfdi:CfdiRelacionado UUID="BBBBBBBB-0000-0000-0000-000000000001"/>'
            "</cfdi:CfdiRelacionados>"
        )
        document = self._create_document(voucher_type="E", related=related)
        move = self.env["account.move"].browse(
            self._create_invoices(document)[1]["res_id"]
        )
        self.assertEqual(
            move.l10n_mx_edi_cfdi_origin, "01|BBBBBBBB-0000-0000-0000-000000000001"
        )

    def test_cancelled_in_sat(self):
        document = self._create_document()
        with patch(_FETCH, return_value={"value": "cancelled"}):
            with self.assertRaisesRegex(UserError, "cancelled"):
                self._create_invoices(document)
        self.assertEqual(document.sat_status, "cancelled")

    def test_not_found_in_sat(self):
        document = self._create_document()
        with patch(_FETCH, return_value={"value": "not_found"}):
            with self.assertRaisesRegex(UserError, "not found"):
                self._create_invoices(document)

    @mute_logger(
        "odoo.addons.l10n_mx_sat_invoice_enterprise.models.l10n_mx_sat_document"
    )
    def test_sat_unreachable_does_not_block(self):
        document = self._create_document()
        with patch(_FETCH, return_value={"value": "error", "error": "timeout"}):
            self._create_invoices(document)
        self.assertTrue(document.vendor_bill_id)

    def test_fiscal_folio_already_registered(self):
        document = self._create_document()
        self._create_invoices(document)
        # Unlink the SAT document to prove the fiscal folio check alone blocks it.
        document._sat_write({"vendor_bill_id": False})
        with self.assertRaisesRegex(UserError, "already registered"):
            self._create_invoices(document)
