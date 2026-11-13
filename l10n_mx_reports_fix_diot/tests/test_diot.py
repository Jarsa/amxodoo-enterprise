from odoo import Command
from odoo.tests import tagged

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon

DATE = "2025-07-01"


@tagged("post_install", "post_install_l10n", "-at_install")
class TestDiotFix(TestAccountReportsCommon):
    @classmethod
    @TestAccountReportsCommon.setup_country("mx")
    def setUpClass(cls):
        super().setUpClass()
        cls.env.companies.tax_exigibility = True
        cls.partner_a.write(
            {
                "country_id": cls.env.ref("base.mx").id,
                "l10n_mx_type_of_operation": "85",
                "vat": "OTE2003102G1",
            }
        )
        cls.diot_report = cls.env.ref("l10n_mx.diot_report")
        cls.handler = cls.env[cls.diot_report.custom_handler_model_name]

    def _tax(self, xmlid):
        return self.env.ref(f"account.{self.env.company.id}_{xmlid}")

    def _post_paid_bill(self, tax, price_unit):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": DATE,
                "date": DATE,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "test",
                            "quantity": 1,
                            "price_unit": price_unit,
                            "tax_ids": [Command.set(tax.ids)],
                        }
                    )
                ],
            }
        )
        bill.action_post()
        self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=bill.ids
        ).create(
            {
                "payment_date": DATE,
                "journal_id": self.company_data["default_journal_bank"].id,
                "amount": bill.amount_total,
            }
        )._create_payments()
        return bill

    def _diot_txt_fields(self):
        options = self._generate_options(self.diot_report, DATE, DATE)
        content = self.handler.action_get_diot_txt(options)["file_content"].decode()
        return content.split("|")

    def test_vat_from_rounded_base(self):
        # 5,006.42 * 8% = 400.51 in accounting, but the SAT checks
        # round(5,006.42) * 8% = 400.48 -> 400, not round(400.51) = 401.
        bill = self._post_paid_bill(self._tax("tax16"), 5006.42)
        self.assertEqual(bill.amount_tax, 400.51)
        fields = self._diot_txt_fields()
        self.assertEqual(fields[7], "5006")
        self.assertEqual(fields[17], "400")

    def test_sat_round_half_down(self):
        # Python rounds 1,001.50 to the even 1,002; the SAT rule gives 1,001.
        self._post_paid_bill(self._tax("tax14"), 1001.50)
        fields = self._diot_txt_fields()
        self.assertEqual(fields[11], "1001")
        self.assertEqual(fields[21], "160")

    def test_sat_round_above_half_up(self):
        self._post_paid_bill(self._tax("tax14"), 1000.51)
        fields = self._diot_txt_fields()
        self.assertEqual(fields[11], "1001")
        self.assertEqual(fields[21], "160")

    def test_non_creditable_vat_column(self):
        # 100.60 * 16% = 16.10; the SAT applet expects it in the column next
        # to the one Odoo fills, and computed from round(100.60) = 101.
        self._post_paid_bill(self._tax("tax18"), 100.60)
        fields = self._diot_txt_fields()
        self.assertEqual(fields[11], "101")
        self.assertEqual(fields[35], "")
        self.assertEqual(fields[36], "16")

    def test_partially_creditable_vat_kept(self):
        # A VAT amount that does not match base * rate (e.g. partially
        # creditable) must keep the accounting amount, only rounded.
        tax = self._tax("tax14")
        repartition = tax.invoice_repartition_line_ids
        base_tags = repartition.filtered(
            lambda line: line.repartition_type == "base"
        ).tag_ids.filtered(lambda tag: "DIOT" in tag.name)
        tax_tags = repartition.filtered(
            lambda line: line.repartition_type == "tax"
        ).tag_ids.filtered(lambda tag: "DIOT" in tag.name)
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": DATE,
                "partner_id": self.partner_a.id,
                "line_ids": [
                    Command.create(
                        {
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "partner_id": self.partner_a.id,
                            "debit": 1000.40,
                            "tax_tag_ids": [Command.set(base_tags.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "account_id": self.company_data[
                                "default_account_tax_purchase"
                            ].id,
                            "partner_id": self.partner_a.id,
                            "debit": 100.60,
                            "tax_tag_ids": [Command.set(tax_tags.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "account_id": self.company_data[
                                "default_account_payable"
                            ].id,
                            "partner_id": self.partner_a.id,
                            "credit": 1101.00,
                        }
                    ),
                ],
            }
        )
        move.action_post()
        fields = self._diot_txt_fields()
        self.assertEqual(fields[11], "1000")
        self.assertEqual(fields[21], "101")
