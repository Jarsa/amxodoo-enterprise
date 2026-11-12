from odoo import Command, fields
from odoo.tests import tagged

from .common import TestCfdiPaymentFollowupCommon, _first_day_next_month


@tagged("post_install", "-at_install")
class TestChatterUpload(TestCfdiPaymentFollowupCommon):
    """Payments and bank statement lines have their own chatter: an XML
    uploaded there must be processed on their journal entry."""

    def setUp(self):
        super().setUp()
        self.payment.move_id.l10n_mx_edi_cfdi_payment_state = "pending"

    def _create_attachment(self, record, xml_bytes):
        return self.env["ir.attachment"].create(
            {
                "name": "complement.xml",
                "raw": xml_bytes,
                "res_model": record._name,
                "res_id": record.id,
                "mimetype": "application/xml",
            }
        )

    def test_payment_related_fields(self):
        """The payment shows the follow-up fields of its journal entry."""
        move = self.payment.move_id
        self.assertEqual(self.payment.l10n_mx_edi_cfdi_payment_state, "pending")
        self.payment.write(
            {
                "l10n_mx_edi_cfdi_payment_receipt": "JVBERi0xLjQK",
                "l10n_mx_edi_cfdi_payment_receipt_filename": "voucher.pdf",
            }
        )
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_receipt_filename, "voucher.pdf")
        self.assertTrue(move.l10n_mx_edi_cfdi_payment_receipt)

    def test_xml_posted_on_payment_chatter(self):
        """An XML posted in the payment chatter validates its journal entry."""
        xml = self._build_cfdi_xml(
            payment_uuid="PAY-UUID-CHATTER-0001",
            payment_date=fields.Date.today(),
            amount=5000.0,
            invoice_uuids=[self.invoice_uuid],
        )
        attachment = self._create_attachment(self.payment, xml)
        self.payment.message_post(body="Complement", attachment_ids=attachment.ids)
        self.assertEqual(self.payment.l10n_mx_edi_cfdi_payment_state, "validated")
        self.assertEqual(self.payment.l10n_mx_edi_cfdi_uuid, "PAY-UUID-CHATTER-0001")

    def test_xml_uploaded_on_payment(self):
        """An XML uploaded to the payment attachments validates its entry."""
        xml = self._build_cfdi_xml(
            payment_uuid="PAY-UUID-UPLOAD-0001",
            payment_date=fields.Date.today(),
            amount=5000.0,
            invoice_uuids=[self.invoice_uuid],
        )
        self._create_attachment(self.payment, xml)._post_add_create()
        self.assertEqual(self.payment.l10n_mx_edi_cfdi_payment_state, "validated")

    def test_xml_posted_on_statement_line_chatter(self):
        """An XML posted in the bank reconciliation chatter (statement line)
        validates the statement line journal entry."""
        suspense = self.env["account.account"].create(
            {
                "name": "Suspense Test",
                "code": "TEST.SUS",
                "account_type": "asset_current",
                "company_ids": [Command.link(self.company_mx.id)],
            }
        )
        self.bank_journal.suspense_account_id = suspense
        today = fields.Date.today()
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.customer.id,
                "company_id": self.company_mx.id,
                "journal_id": self.sale_journal.id,
                "invoice_date": today,
                "invoice_date_due": _first_day_next_month(today),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Service Test",
                            "price_unit": 1200.0,
                            "account_id": self.account_income.id,
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        invoice_uuid = "INVOICE-UUID-0000-0000-TEST-0002"
        self._stamp_invoice(invoice, invoice_uuid)
        st_line = self.env["account.bank.statement.line"].create(
            {
                "journal_id": self.bank_journal.id,
                "date": today,
                "payment_ref": "SPEI customer",
                "partner_id": self.customer.id,
                "amount": 1200.0,
            }
        )
        receivable = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        st_line.set_line_bank_statement_line(receivable.ids)
        self.assertEqual(st_line.l10n_mx_edi_cfdi_payment_state, "pending")

        xml = self._build_cfdi_xml(
            payment_uuid="PAY-UUID-STLINE-0001",
            payment_date=today,
            amount=1200.0,
            invoice_uuids=[invoice_uuid],
        )
        attachment = self._create_attachment(st_line, xml)
        st_line.message_post(body="Complement", attachment_ids=attachment.ids)
        self.assertEqual(st_line.l10n_mx_edi_cfdi_payment_state, "validated")
