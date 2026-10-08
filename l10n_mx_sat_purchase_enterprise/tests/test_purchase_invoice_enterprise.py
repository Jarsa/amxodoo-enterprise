# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.l10n_mx_sat_purchase.tests.test_purchase_invoice_wizard import (
    TestPurchaseInvoiceWizard,
)

_FETCH = (
    "odoo.addons.l10n_mx_edi.models.l10n_mx_edi_document."
    "L10n_Mx_EdiDocument._fetch_sat_status"
)


@tagged("post_install", "-at_install")
class TestPurchaseInvoiceEnterprise(TestPurchaseInvoiceWizard):
    """Re-run the base tests with l10n_mx_edi and add the Enterprise checks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.startClassPatcher(patch(_FETCH, return_value={"value": "valid"}))

    def test_create_bill_edi_document(self):
        self.test_create_bill()
        move = self.order.invoice_ids
        self.assertEqual(move.l10n_mx_edi_cfdi_uuid, self.document.uuid)
        edi_document = move.l10n_mx_edi_document_ids
        self.assertEqual(edi_document.state, "invoice_received")
        self.assertEqual(edi_document.sat_state, "valid")
        self.assertEqual(self.document.sat_status, "valid")

    def test_cancelled_in_sat(self):
        wizard = self._open_wizard()
        with patch(_FETCH, return_value={"value": "cancelled"}):
            self.assertRejected(wizard.action_create_invoice())
        self.assertEqual(self.document.sat_status, "cancelled")
        self.assertNotIn(
            self.document, self._open_wizard().l10n_mx_sat_available_document_ids
        )

    def test_not_found_in_sat(self):
        wizard = self._open_wizard()
        with patch(_FETCH, return_value={"value": "not_found"}):
            self.assertRejected(wizard.action_create_invoice())

    def test_sat_unreachable_does_not_block(self):
        wizard = self._open_wizard()
        with patch(_FETCH, return_value={"value": "error", "error": "timeout"}):
            wizard.action_create_invoice()
        self.assertEqual(self.document.vendor_bill_id, self.order.invoice_ids)

    def test_fiscal_folio_already_registered(self):
        self._open_wizard().action_create_invoice()
        second_order = self._create_order()
        wizard = self._open_wizard(second_order)
        self.assertNotIn(self.document, wizard.l10n_mx_sat_available_document_ids)
        # Unlink the SAT document to prove the fiscal folio check alone blocks it.
        self.document._sat_write({"vendor_bill_id": False})
        action = self._open_wizard(second_order).action_create_invoice()
        self.assertEqual(action["tag"], "display_notification")
        self.assertFalse(second_order.invoice_ids)
