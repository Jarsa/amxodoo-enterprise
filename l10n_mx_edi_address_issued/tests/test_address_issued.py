from lxml import etree

from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon

CFDI_NS = "http://www.sat.gob.mx/cfd/4"


@tagged("post_install_l10n", "post_install", "-at_install")
class TestAddressIssued(TestMxEdiCommon):
    """For a foreign customer the SAT requires DomicilioFiscalReceptor to be
    equal to LugarExpedicion (CFDI40149). In multi-branch environments both must
    be the branch ZIP configured on the journal (l10n_mx_address_issued_id).

    Invoices and credit notes are handled by l10n_mx_edi_extended; this module
    adds the same behaviour to the payment complement. These tests assert all
    three flows produce matching branch values.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        branch_vals = {
            "type": "invoice",
            "state_id": cls.env.ref("base.state_mx_chih").id,
            "country_id": cls.env.ref("base.mx").id,
        }
        cls.branch_a = cls.env["res.partner"].create(
            {"name": "Sucursal A", "zip": "32472", **branch_vals}
        )
        cls.branch_b = cls.env["res.partner"].create(
            {"name": "Sucursal B", "zip": "44650", **branch_vals}
        )
        cls.journal_a = cls.company_data["default_journal_sale"]
        cls.journal_a.l10n_mx_address_issued_id = cls.branch_a
        cls.journal_b = cls.journal_a.copy({"name": "Sale B", "code": "INVB"})
        cls.journal_b.l10n_mx_address_issued_id = cls.branch_b

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _foreign_invoice(self, move_type="out_invoice", journal=None):
        return self._create_invoice(
            move_type=move_type,
            partner_id=self.partner_us.id,
            journal_id=(journal or self.journal_a).id,
            invoice_line_ids=[
                Command.create(
                    {
                        "product_id": self.product.id,
                        "price_unit": 1000.0,
                        "tax_ids": [Command.set(self.tax_16.ids)],
                    }
                )
            ],
        )

    def _cfdi(self, document):
        return etree.fromstring(document.attachment_id.raw)

    def _lugar_and_domicilio(self, cfdi):
        receptor = cfdi.find(f"{{{CFDI_NS}}}Receptor")
        return (
            cfdi.get("LugarExpedicion"),
            receptor.get("DomicilioFiscalReceptor"),
        )

    # -------------------------------------------------------------------------
    # Integration: invoice / credit note / payment must use the branch ZIP
    # -------------------------------------------------------------------------

    def test_invoice_foreign_uses_branch_address(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._foreign_invoice()
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            document = invoice.l10n_mx_edi_invoice_document_ids.filtered(
                lambda d: d.state == "invoice_sent"
            )[:1]
            self.assertTrue(document, "Invoice CFDI not generated")
            lugar, domicilio = self._lugar_and_domicilio(self._cfdi(document))
            self.assertEqual(lugar, "32472")
            self.assertEqual(domicilio, "32472")

    def test_credit_note_foreign_uses_branch_address(self):
        with self.mx_external_setup(self.frozen_today):
            refund = self._foreign_invoice(move_type="out_refund")
            with self.with_mocked_pac_sign_success():
                refund._l10n_mx_edi_cfdi_invoice_try_send()
            document = refund.l10n_mx_edi_invoice_document_ids.filtered(
                lambda d: d.state == "invoice_sent"
            )[:1]
            self.assertTrue(document, "Credit note CFDI not generated")
            lugar, domicilio = self._lugar_and_domicilio(self._cfdi(document))
            self.assertEqual(lugar, "32472")
            self.assertEqual(domicilio, "32472")

    def test_payment_foreign_matches_invoice(self):
        with self.mx_external_setup(self.frozen_today):
            invoice = self._foreign_invoice()
            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()
            self.assertTrue(
                invoice.l10n_mx_edi_invoice_document_ids.filtered(
                    lambda d: d.state == "invoice_sent"
                )
            )

            payment = self._create_payment(invoice)
            with self.with_mocked_pac_sign_success():
                payment.move_id._l10n_mx_edi_cfdi_payment_try_send()
            document = payment.move_id.l10n_mx_edi_payment_document_ids.filtered(
                lambda d: d.state == "payment_sent"
            )[:1]
            self.assertTrue(document, "Payment CFDI not generated")
            # Without this module LugarExpedicion would be the company HQ ZIP,
            # breaking CFDI40149 against the branch DomicilioFiscalReceptor.
            lugar, domicilio = self._lugar_and_domicilio(self._cfdi(document))
            self.assertEqual(lugar, "32472")
            self.assertEqual(domicilio, "32472")
            self.assertEqual(lugar, domicilio)

    # -------------------------------------------------------------------------
    # Unit: branch selection / mixed-branch guard (no PAC needed)
    # -------------------------------------------------------------------------

    def _pay_results(self, *journals):
        return {
            "invoice_results": [
                {"invoice": self._create_invoice(journal_id=journal.id)}
                for journal in journals
            ]
        }

    def test_single_branch_returns_its_address(self):
        address, error = self.env["account.move"]._l10n_mx_edi_payment_issued_address(
            self._pay_results(self.journal_a)
        )
        self.assertFalse(error)
        self.assertEqual(address, self.branch_a)
        self.assertEqual(address.zip, "32472")

    def test_mixed_branches_block_with_error(self):
        address, error = self.env["account.move"]._l10n_mx_edi_payment_issued_address(
            self._pay_results(self.journal_a, self.journal_b)
        )
        self.assertTrue(error)
        self.assertFalse(address)

    def test_no_branch_returns_empty(self):
        self.journal_a.l10n_mx_address_issued_id = False
        address, error = self.env["account.move"]._l10n_mx_edi_payment_issued_address(
            self._pay_results(self.journal_a)
        )
        self.assertFalse(error)
        self.assertFalse(address)
