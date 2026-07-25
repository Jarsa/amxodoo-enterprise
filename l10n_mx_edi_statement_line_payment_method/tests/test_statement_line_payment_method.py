from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStatementLinePaymentMethod(TransactionCase):
    def test_payment_method_delegation(self):
        """The payment method set on the statement line must reach its journal entry,
        which is the value used to render the CFDI payment complement."""
        journal = self.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )
        payment_method = self.env["l10n_mx_edi.payment.method"].search([], limit=1)
        statement_line = self.env["account.bank.statement.line"].create(
            {
                "journal_id": journal.id,
                "payment_ref": "Test payment method",
                "amount": 100.0,
                "date": "2026-01-01",
                "l10n_mx_edi_payment_method_id": payment_method.id,
            }
        )
        self.assertEqual(
            statement_line.move_id.l10n_mx_edi_payment_method_id,
            payment_method,
        )
