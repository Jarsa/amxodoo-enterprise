from unittest.mock import patch

from lxml import etree
from lxml import html as lxml_html

from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

PAYMENT_REPORT = "account.report_payment_receipt"
BANK_TRANSACTION_REPORT = "l10n_mx_edi.report_bank_transaction_receipt"
PAYMENT_INFO_TABLE = "//table[@name='table_l10n_mx_edi_payment_info']"
PARTIALITY_TABLE = "//table[@name='table_l10n_mx_edi_invoice_partiality_info']"
MODULE = "l10n_mx_edi_account_move_payment_report"


@tagged("post_install_l10n", "post_install", "-at_install")
class TestPaymentReport(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.invoice = cls.init_invoice(
            "out_invoice", partner=cls.partner_a, amounts=[3000.0], post=True
        )
        cls.payment = (
            cls.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=cls.invoice.ids)
            .create({"amount": 1000.0})
            ._create_payments()
        )
        cls.statement_line = cls.env["account.bank.statement.line"].create(
            {
                "journal_id": cls.company_data["default_journal_bank"].id,
                "partner_id": cls.partner_a.id,
                "payment_ref": "Bank transaction",
                "amount": 1234.5,
                "date": "2026-01-15",
            }
        )
        cls.statement_move = cls.statement_line.move_id
        cls.statement_move.write(
            {
                "ref": "MEMO-0001",
                "l10n_mx_edi_payment_method_id": cls.env.ref(
                    "l10n_mx_edi.payment_method_transferencia"
                ).id,
            }
        )
        cls.partner_a.l10n_mx_edi_fiscal_regime = "601"
        cls.env.company.vat = "EKU9003173C9"

    def _fake_cfdi(self, supplier_rfc="XIA190128J61"):
        """CFDI values as l10n_mx_edi returns them for a stamped payment."""
        return {
            "cfdi_node": etree.fromstring("<Comprobante><Pago/></Comprobante>"),
            "payment_info": {
                "from_account_vat": "BBA830831LJ2",
                "from_account_name": False,
                "from_account_number": "1234567890",
                "to_account_vat": False,
                "to_account_number": False,
            },
            "invoices": [
                {
                    "uuid": "UUID-INV-0001",
                    "partiality": "1",
                    "previous_balance": 3000.0,
                    "amount_paid": 1000.0,
                    "balance": 2000.0,
                    "currency": self.invoice.currency_id.name,
                    "invoice": self.invoice,
                }
            ],
            "supplier_rfc": supplier_rfc,
            "barcode_src": "/report/barcode/?barcode_type=QR&value=x",
            "sello": "SELLO-EMISOR",
            "sello_sat": "SELLO-SAT",
            "cadena": "CADENA-ORIGINAL",
            "certificate_number": "00001",
            "certificate_sat_number": "00002",
            "expedition": "64000",
            "fiscal_regime": "601",
            "emission_date_str": "2026-01-15T10:00:00",
            "stamp_date": "2026-01-15T10:00:01",
            "uuid": "UUID-PAY-0001",
        }

    def _document(self, move, state):
        return self.env["l10n_mx_edi.document"].create(
            {
                "move_id": move.id,
                "company_id": move.company_id.id,
                "state": state,
                "datetime": "2026-01-15 10:00:00",
            }
        )

    def _render(self, report, records, cfdi=None):
        move_class = type(self.env["account.move"])
        with patch.object(
            move_class,
            "_l10n_mx_edi_get_extra_payment_report_values",
            lambda move: cfdi or {},
        ):
            html, report_type = self.env["ir.actions.report"]._render_qweb_html(
                report, records.ids
            )
        self.assertEqual(report_type, "html")
        return lxml_html.fromstring(html.decode())

    def _text(self, doc, name):
        nodes = doc.xpath(f"//*[@name='{name}']")
        return " ".join(nodes[0].text_content().split()) if nodes else None

    def test_payment_receipt(self):
        """The payment receipt shows both VATs and the customer fiscal regime."""
        doc = self._render(PAYMENT_REPORT, self.payment, cfdi=self._fake_cfdi())
        self.assertEqual(
            self._text(doc, "l10n_mx_edi_supplier_rfc"),
            "XML VAT: EKU9003173C9 XIA190128J61",
        )
        self.assertEqual(
            self._text(doc, "fiscal_regime"),
            "Fiscal Regime: (601) General de Ley Personas Morales",
        )

    def test_payment_receipt_payment_way(self):
        """The SAT payment way is shown once: natively with CFDI, by this module
        without CFDI (PUE)."""
        self.payment.l10n_mx_edi_payment_method_id = self.env.ref(
            "l10n_mx_edi.payment_method_transferencia"
        )
        expected = "Payment Way: 03 - Transferencia electrónica de fondos"
        doc = self._render(PAYMENT_REPORT, self.payment)
        self.assertEqual(self._text(doc, "l10n_mx_edi_payment_method_pue"), expected)
        self.assertIsNone(self._text(doc, "l10n_mx_edi_payment_method"))
        doc = self._render(PAYMENT_REPORT, self.payment, cfdi=self._fake_cfdi())
        self.assertEqual(self._text(doc, "l10n_mx_edi_payment_method"), expected)
        self.assertIsNone(self._text(doc, "l10n_mx_edi_payment_method_pue"))

    def test_payment_receipt_without_stamp(self):
        """The fiscal regime is shown only once the CFDI is stamped."""
        doc = self._render(PAYMENT_REPORT, self.payment)
        self.assertIsNone(self._text(doc, "fiscal_regime"))
        cfdi = self._fake_cfdi()
        cfdi["sello_sat"] = False
        doc = self._render(PAYMENT_REPORT, self.payment, cfdi=cfdi)
        self.assertIsNone(self._text(doc, "fiscal_regime"))

    def test_bank_transaction_receipt(self):
        """The bank transaction receipt shows the XML VAT, payment method, memo,
        fiscal regime, the bank accounts of the CFDI and the CFDI tables."""
        doc = self._render(
            BANK_TRANSACTION_REPORT, self.statement_move, cfdi=self._fake_cfdi()
        )
        self.assertEqual(
            self._text(doc, "l10n_mx_edi_supplier_rfc"),
            "XML VAT: EKU9003173C9 XIA190128J61",
        )
        # The native Payment Way is shown, not a duplicated Payment Method
        self.assertEqual(
            self._text(doc, "l10n_mx_edi_payment_method"),
            "Payment Way: 03 - Transferencia electrónica de fondos",
        )
        self.assertIsNone(self._text(doc, "payment_method"))
        self.assertEqual(self._text(doc, "memo"), "Memo: MEMO-0001")
        self.assertEqual(
            self._text(doc, "fiscal_regime"),
            "Fiscal Regime: (601) General de Ley Personas Morales",
        )
        self.assertTrue(doc.xpath(PARTIALITY_TABLE))
        table = doc.xpath(PAYMENT_INFO_TABLE)
        self.assertEqual(len(table), 1)
        cells = [
            " ".join(td.text_content().split())
            for td in table[0].xpath("./tbody/tr/td")
        ]
        self.assertEqual(cells, ["BBA830831LJ2", "1234567890"])
        headers = [
            " ".join(th.text_content().split())
            for th in table[0].xpath("./thead/tr/th")
        ]
        self.assertEqual(len(headers), 2)
        self.assertTrue(headers[0].endswith("Emitter Acc. Ord."))
        self.assertEqual(headers[1], "Account Ord.")

    def test_bank_transaction_receipt_same_vat(self):
        """The XML VAT is hidden when the CFDI was issued with the company VAT."""
        doc = self._render(
            BANK_TRANSACTION_REPORT,
            self.statement_move,
            cfdi=self._fake_cfdi(supplier_rfc="EKU9003173C9"),
        )
        self.assertIsNone(self._text(doc, "l10n_mx_edi_supplier_rfc"))

    def test_bank_transaction_receipt_without_cfdi(self):
        """Without CFDI (PUE) only the payment method and memo are added."""
        doc = self._render(BANK_TRANSACTION_REPORT, self.statement_move)
        self.assertEqual(
            self._text(doc, "payment_method"),
            "Payment Method: Transferencia electrónica de fondos",
        )
        self.assertEqual(self._text(doc, "memo"), "Memo: MEMO-0001")
        self.assertIsNone(self._text(doc, "l10n_mx_edi_supplier_rfc"))
        self.assertIsNone(self._text(doc, "fiscal_regime"))
        self.assertFalse(doc.xpath(PAYMENT_INFO_TABLE))
        self.assertFalse(doc.xpath(PARTIALITY_TABLE))

    def test_print_button_pue(self):
        """The Print button of the CFDI documents is also shown for PUE payments."""
        for state, needed in (
            ("payment_sent_pue", True),
            ("payment_sent", True),
            ("payment_sent_failed", False),
        ):
            document = self._document(self.statement_move, state)
            self.assertEqual(document.print_button_needed, needed, state)
        document = self._document(self.statement_move, "payment_sent_pue")
        action = document.with_context(
            discard_logo_check=True
        ).action_download_payment_receipt()
        self.assertEqual(action["report_name"], BANK_TRANSACTION_REPORT)

    def test_send_bank_transaction_receipt(self):
        """The receipt of a bank transaction is sent from the move with its
        report and the CFDI XML."""
        action = self._document(
            self.statement_move, "payment_sent"
        ).action_send_payment_email()
        template = self.env.ref(f"{MODULE}.mail_template_data_bank_transaction_receipt")
        self.assertEqual(action["res_model"], "mail.compose.message")
        self.assertEqual(action["context"]["default_model"], "account.move")
        self.assertEqual(action["context"]["default_res_ids"], self.statement_move.ids)
        self.assertEqual(action["context"]["default_template_id"], template.id)
        self.assertNotIn("mail_post_autofollow", action["context"])
        report = self.env.ref("l10n_mx_edi.action_report_bank_transaction_receipt")
        self.assertEqual(template.report_template_ids, report)
        self.assertEqual(
            safe_eval(report.print_report_name, {"object": self.statement_move}),
            f"Payment Receipt - {self.statement_move.name}",
        )

        xml = self.env["ir.attachment"].create(
            {
                "name": "cfdi.xml",
                "raw": b"<cfdi/>",
                "res_model": "account.move",
                "res_id": self.statement_move.id,
            }
        )
        self.statement_move.l10n_mx_edi_cfdi_attachment_id = xml
        values = template._generate_template(
            self.statement_move.ids, ("attachment_ids", "subject", "partner_to")
        )[self.statement_move.id]
        self.assertEqual(values["attachment_ids"], xml.ids)
        self.assertEqual(values["partner_ids"], self.partner_a.ids)
        self.assertIn(self.statement_move.name, values["subject"])

        # Other templates of the move do not get the CFDI XML
        other = self.env.ref("account.email_template_edi_credit_note")
        other_values = other._generate_template(
            self.statement_move.ids, ("attachment_ids",)
        )[self.statement_move.id]
        self.assertNotIn(xml.id, other_values.get("attachment_ids", []))

    def test_bank_transaction_receipt_filename_translated(self):
        """The file name of the bank transaction receipt is translated."""
        self.env["res.lang"]._activate_lang("es_MX")
        report = self.env.ref("l10n_mx_edi.action_report_bank_transaction_receipt")
        move = self.statement_move.with_context(lang="es_MX")
        self.assertEqual(
            safe_eval(report.print_report_name, {"object": move}),
            f"Recibo de Pago - {move.name}",
        )

    def test_send_without_template(self):
        """The composer opens without template if the template was deleted."""
        self.env.ref(f"{MODULE}.mail_template_data_bank_transaction_receipt").unlink()
        action = self._document(
            self.statement_move, "payment_sent"
        ).action_send_payment_email()
        self.assertFalse(action["context"]["default_template_id"])
        self.env.ref("account.mail_template_data_payment_receipt").unlink()
        action = self._document(
            self.payment.move_id, "payment_sent"
        ).action_send_payment_email()
        self.assertFalse(action["context"]["default_template_id"])

    def test_send_payment_receipt(self):
        """The receipt of a payment is sent with the native payment template."""
        action = self._document(
            self.payment.move_id, "payment_sent_pue"
        ).action_send_payment_email()
        self.assertEqual(action["context"]["default_model"], "account.payment")
        self.assertEqual(action["context"]["default_res_ids"], self.payment.ids)
        self.assertTrue(action["context"]["mail_post_autofollow"])
        self.assertEqual(
            action["context"]["default_template_id"],
            self.env.ref("account.mail_template_data_payment_receipt").id,
        )

    def test_fiscal_folio_column(self):
        """The bank reconciliation list has the optional Fiscal Folio column."""
        view = self.env.ref(
            "account_accountant.view_bank_statement_line_tree_bank_rec_widget"
        )
        arch = etree.fromstring(
            self.env["account.bank.statement.line"].get_view(view.id)["arch"]
        )
        self.assertTrue(
            arch.xpath("//field[@name='l10n_mx_edi_cfdi_uuid'][@optional='hide']")
        )
        self.statement_move.l10n_mx_edi_cfdi_uuid = "UUID-LINE-0001"
        lines = self.env["account.bank.statement.line"].search(
            [("l10n_mx_edi_cfdi_uuid", "=", "UUID-LINE-0001")],
            order="l10n_mx_edi_cfdi_uuid",
        )
        self.assertEqual(lines, self.statement_line)
