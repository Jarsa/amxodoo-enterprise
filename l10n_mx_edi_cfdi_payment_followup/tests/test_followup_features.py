from odoo import Command, fields

from .common import TestCfdiPaymentFollowupCommon, _first_day_next_month


class TestCfdiFollowupFeatures(TestCfdiPaymentFollowupCommon):
    # ---- Point 1: request email helpers ------------------------------------

    def test_reconciled_invoice_details_partial(self):
        """The details helper returns the applied (partial) amount per invoice."""
        details = self.payment.move_id._get_cfdi_reconciled_invoice_details()
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]["invoice"], self.invoice)
        self.assertAlmostEqual(details[0]["amount"], 5000.0)

    def test_request_email_attaches_receipt_only(self):
        """The complement request attaches the receipt field, nothing else."""
        move = self.payment.move_id
        move.write(
            {
                "l10n_mx_edi_cfdi_payment_receipt": b"JVBERi0xLjQK",  # 'pdf' bytes b64
                "l10n_mx_edi_cfdi_payment_receipt_filename": "voucher.pdf",
            }
        )
        self.customer.email = "vendor@example.com"
        self.payment.action_request_cfdi_complement()
        mail = self.env["mail.mail"].search(
            [("model", "=", "account.move"), ("res_id", "=", move.id)],
            order="id desc",
            limit=1,
        )
        self.assertTrue(mail)
        self.assertEqual(len(mail.attachment_ids), 1)
        self.assertEqual(mail.attachment_ids.name, "voucher.pdf")

    # ---- Point 2: supplier vs customer payment -----------------------------

    def test_is_supplier_payment_flag(self):
        """The flag is False for a customer collection, True for a vendor bill."""
        self.assertFalse(self.payment.move_id.l10n_mx_edi_cfdi_is_supplier_payment)

        purchase_journal = self.env["account.journal"].create(
            {
                "name": "Purchase Test MX",
                "type": "purchase",
                "code": "PURT",
                "company_id": self.company_mx.id,
            }
        )
        today = fields.Date.today()
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.customer.id,
                "company_id": self.company_mx.id,
                "journal_id": purchase_journal.id,
                "invoice_date": today,
                "invoice_date_due": _first_day_next_month(today),
                "ref": "VENDOR-FOLIO-001",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Vendor Service",
                            "price_unit": 3000.0,
                            "account_id": self.account_income.id,
                        }
                    )
                ],
            }
        )
        bill.action_post()
        vendor_payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.customer.id,
                "amount": 3000.0,
                "currency_id": self.mxn.id,
                "journal_id": self.bank_journal.id,
                "date": today,
                "company_id": self.company_mx.id,
            }
        )
        vendor_payment.action_post()
        pay_line = vendor_payment.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type == "liability_payable"
        )
        bill_line = bill.line_ids.filtered(
            lambda line: line.account_id.account_type == "liability_payable"
        )
        (pay_line | bill_line).reconcile()
        self.assertTrue(vendor_payment.move_id.l10n_mx_edi_cfdi_is_supplier_payment)

    # ---- Point 3: ignore / revert ------------------------------------------

    def test_ignore_sets_not_required_and_persists(self):
        """Ignoring sets Not Required and survives a recomputation."""
        move = self.payment.move_id
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "pending")
        self.payment.action_cfdi_ignore()
        self.assertTrue(move.l10n_mx_edi_cfdi_payment_manual_ignore)
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "not_required")
        # Force a recomputation: the ignore must still hold.
        move.invalidate_recordset()
        move._compute_l10n_mx_edi_cfdi_payment_state()
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "not_required")

    def test_unignore_reverts_to_pending(self):
        """Reverting the ignore recomputes the state back to Pending."""
        move = self.payment.move_id
        self.payment.action_cfdi_ignore()
        self.payment.action_cfdi_unignore()
        self.assertFalse(move.l10n_mx_edi_cfdi_payment_manual_ignore)
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "pending")

    # ---- Point 4: valid XML wins over an ignored payment -------------------

    def test_valid_xml_overrides_ignore(self):
        """A received valid XML validates even if the payment was ignored."""
        move = self.payment.move_id
        self.payment.action_cfdi_ignore()
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "not_required")
        xml = self._build_cfdi_xml(
            payment_uuid="PAY-UUID-OVR-0001",
            payment_date=fields.Date.today(),
            amount=5000.0,
            invoice_uuids=[self.invoice_uuid],
        )
        self._attach_xml(move, xml)
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "validated")
        self.assertFalse(move.l10n_mx_edi_cfdi_payment_manual_ignore)
