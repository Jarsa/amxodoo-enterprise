from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPaymentReport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document = cls.env["l10n_mx_edi.document"].create(
            {
                "datetime": fields.Datetime.now(),
                "state": "payment_sent",
            }
        )

    def test_action_print_payment(self):
        action = self.document.with_context(
            discard_logo_check=True
        ).action_print_payment()
        self.assertEqual(
            action["report_name"],
            "l10n_mx_edi_account_move_payment_report.report_payment_receipt_invoice_template",
        )

    def test_action_send_payment_email(self):
        action = self.document.action_send_payment_email()
        template = self.env.ref(
            "l10n_mx_edi_account_move_payment_report.mail_template_data_payment_receipt"
        )
        self.assertEqual(action["res_model"], "mail.compose.message")
        self.assertEqual(action["context"]["default_template_id"], template.id)
        self.assertEqual(action["context"]["default_res_ids"], self.document.ids)

    def test_payment_report_values_without_attachment(self):
        self.assertEqual(
            self.document._l10n_mx_edi_get_extra_payment_report_values(), {}
        )
