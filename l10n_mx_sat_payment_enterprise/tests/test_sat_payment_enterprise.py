# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.l10n_mx_sat_invoice_enterprise.tests.test_invoice_enterprise import (
    _FETCH,
)
from odoo.addons.l10n_mx_sat_payment.tests.test_sat_payment import TestSatPayment


@tagged("post_install", "-at_install")
class TestSatPaymentEnterprise(TestSatPayment):
    """Re-run the base tests with l10n_mx_edi and add the Enterprise checks."""

    allow_inherited_tests_method = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.startClassPatcher(patch(_FETCH, return_value={"value": "valid"}))

    def test_issued_payment_edi_document(self):
        document, move = self._posted_invoice()
        complement = self._create_complement({document: 1160})
        complement.action_apply_payments()
        payment = complement.sat_payment_ids.payment_id
        self.assertRecordValues(
            payment,
            [
                {
                    "l10n_mx_edi_cfdi_uuid": complement.uuid,
                    "l10n_mx_edi_cfdi_state": "sent",
                    "l10n_mx_edi_cfdi_sat_state": "valid",
                }
            ],
        )
        self.assertEqual(payment.l10n_mx_edi_payment_method_id.code, "03")
        self.assertEqual(payment.l10n_mx_edi_payment_document_ids.invoice_ids, move)

    def test_received_payment_no_edi_document(self):
        document, _move = self._posted_invoice(direction="received")
        complement = self._create_complement({document: 1160}, direction="received")
        complement.action_apply_payments()
        payment = complement.sat_payment_ids.payment_id
        self.assertFalse(payment.l10n_mx_edi_cfdi_uuid)
        self.assertEqual(payment.l10n_mx_edi_payment_method_id.code, "03")

    def test_find_invoice_by_fiscal_folio(self):
        document, move = self._posted_invoice()
        # Without the SAT link the invoice is still found by its fiscal folio
        document._sat_write({"customer_invoice_id": False})
        complement = self._create_complement({document: 1160})
        self.assertEqual(complement.sat_payment_ids.line_ids.invoice_id, move)
        complement.action_apply_payments()
        self.assertEqual(complement.sat_payment_state, "done")
