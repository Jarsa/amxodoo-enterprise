# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from unittest.mock import patch

from odoo import Command
from odoo.tests import HttpCase, tagged

from odoo.addons.l10n_mx_sat_invoice.tests.test_invoice_wizard import (
    CUSTOMER_RFC,
    TestInvoiceWizard,
)

from .test_invoice_enterprise import _FETCH


@tagged("post_install", "-at_install")
class TestStatementLineWizard(TestInvoiceWizard, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.startClassPatcher(patch(_FETCH, return_value={"value": "valid"}))
        cls.user.group_ids += cls.env.ref("account.group_account_user")

    def _create_st_line(self, amount, partner=None):
        return self.env["account.bank.statement.line"].create(
            {
                "amount": amount,
                "date": "2026-02-20",
                "payment_ref": "SPEI",
                "journal_id": self.company_data["default_journal_bank"].id,
                "partner_id": partner and partner.id,
            }
        )

    def _wizard(self, st_line, **vals):
        action = st_line.with_user(self.user).action_l10n_mx_sat_create_invoices()
        return (
            self.env[action["res_model"]]
            .with_user(self.user)
            .with_context(**action["context"])
            .create(vals)
        )

    def test_vendor_payment(self):
        documents = self._create_document() + self._create_document()
        other = self._create_document(issuer=("AAA010101AAA", "OTRO PROVEEDOR"))
        issued = self._create_document(direction="issued")
        st_line = self._create_st_line(-2320, self.vendor)
        wizard = self._wizard(st_line)
        self.assertRecordValues(
            wizard,
            [{"direction": "received", "journal_type": "purchase", "amount": 2320}],
        )
        Document = self.env["l10n_mx_sat.document"]
        self.assertEqual(Document.search(wizard.document_domain), documents)
        wizard.only_partner = False
        candidates = Document.search(wizard.document_domain)
        self.assertIn(other, candidates)
        self.assertNotIn(issued, candidates)
        wizard.document_ids = [Command.set(documents.ids)]
        self.assertEqual(wizard.selected_total, 2320)
        self.assertEqual(wizard.difference, 0)
        wizard.action_create_invoices()
        bills = documents.vendor_bill_id
        self.assertEqual(len(bills), 2)
        self.assertEqual(set(bills.mapped("move_type")), {"in_invoice"})
        self.assertTrue(st_line.is_reconciled)
        payable_lines = bills.line_ids.filtered(
            lambda line: line.account_id.account_type == "liability_payable"
        )
        self.assertTrue(all(payable_lines.mapped("reconciled")))

    def test_customer_partial_payment(self):
        customer = self.env["res.partner"].create(
            {"name": "Cliente Demo", "vat": CUSTOMER_RFC}
        )
        document = self._create_document(direction="issued")
        st_line = self._create_st_line(500, customer)
        wizard = self._wizard(st_line, document_ids=[Command.set(document.ids)])
        self.assertRecordValues(
            wizard,
            [{"direction": "issued", "journal_type": "sale", "difference": -660}],
        )
        wizard.action_create_invoices()
        invoice = document.customer_invoice_id
        self.assertEqual(invoice.move_type, "out_invoice")
        self.assertTrue(st_line.is_reconciled)
        receivable = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        self.assertEqual(receivable.amount_residual, 660)

    def test_tour_bank_reconciliation(self):
        documents = self._create_document() + self._create_document()
        st_line = self._create_st_line(-2320, self.vendor)
        self.start_tour(
            "/odoo",
            "l10n_mx_sat_invoice_enterprise_bank_rec",
            login=self.env.user.login,
        )
        self.assertEqual(len(documents.vendor_bill_id), 2)
        self.assertTrue(st_line.is_reconciled)
