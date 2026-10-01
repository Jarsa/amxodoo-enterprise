from lxml import etree

from odoo import Command, fields

from .common import TestCfdiPaymentFollowupCommon, _first_day_next_month


class TestVendorBillPolicy(TestCfdiPaymentFollowupCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.purchase_journal = cls.env["account.journal"].create(
            {
                "name": "Purchase Test MX",
                "type": "purchase",
                "code": "PURT",
                "company_id": cls.company_mx.id,
            }
        )

    def _create_paid_bill(self, date_due):
        """Return a posted vendor bill and the payment move reconciled with it."""
        today = fields.Date.today()
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.customer.id,
                "company_id": self.company_mx.id,
                "journal_id": self.purchase_journal.id,
                "invoice_date": today,
                "invoice_date_due": date_due,
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
        payment = self.env["account.payment"].create(
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
        payment.action_post()
        (payment.move_id | bill).line_ids.filtered(
            lambda line: line.account_id.account_type == "liability_payable"
        ).reconcile()
        return bill, payment.move_id

    def _attach_bill_cfdi(self, bill, payment_policy):
        """Attach a received CFDI with the given ``MetodoPago`` to the bill."""
        root = etree.Element(
            "{http://www.sat.gob.mx/cfd/4}Comprobante",
            nsmap={"cfdi": "http://www.sat.gob.mx/cfd/4"},
        )
        root.set("TipoDeComprobante", "I")
        root.set("MetodoPago", payment_policy)
        attachment = self.env["ir.attachment"].create(
            {
                "name": "bill.xml",
                "raw": etree.tostring(root, xml_declaration=True, encoding="UTF-8"),
                "res_model": bill._name,
                "res_id": bill.id,
                "mimetype": "application/xml",
            }
        )
        self.env["l10n_mx_edi.document"].create(
            {
                "move_id": bill.id,
                "invoice_ids": [Command.set(bill.ids)],
                "state": "invoice_received",
                "sat_state": "not_defined",
                "attachment_id": attachment.id,
                "datetime": fields.Datetime.now(),
            }
        )

    def test_policy_without_cfdi_uses_computed_field(self):
        """A vendor bill without CFDI falls back to the computed field."""
        bill, payment_move = self._create_paid_bill(_first_day_next_month())
        self.assertEqual(
            bill._get_cfdi_payment_policy(), bill.l10n_mx_edi_payment_policy
        )
        self.assertEqual(payment_move.l10n_mx_edi_cfdi_payment_state, "not_required")

    def test_policy_ppd_from_cfdi(self):
        """The CFDI says PPD although the dates would say PUE: complement due.

        The CFDI is attached once the bill is already paid, so this also covers
        the recomputation of the payment state.
        """
        bill, payment_move = self._create_paid_bill(fields.Date.today())
        self.assertEqual(payment_move.l10n_mx_edi_cfdi_payment_state, "not_required")
        self._attach_bill_cfdi(bill, "PPD")
        self.assertEqual(bill._get_cfdi_payment_policy(), "PPD")
        self.assertEqual(payment_move.l10n_mx_edi_cfdi_payment_state, "pending")

    def test_policy_pue_from_cfdi(self):
        """The CFDI says PUE although the dates would say PPD: no complement."""
        bill, payment_move = self._create_paid_bill(_first_day_next_month())
        self._attach_bill_cfdi(bill, "PUE")
        self.assertEqual(bill._get_cfdi_payment_policy(), "PUE")
        self.assertEqual(payment_move.l10n_mx_edi_cfdi_payment_state, "not_required")
