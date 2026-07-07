from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install_l10n", "post_install", "-at_install")
class TestSatCronFix(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bill = cls.init_invoice(
            "in_invoice",
            invoice_date="2026-01-01",
            amounts=[100.0],
            post=True,
        )
        cls.doc_unchecked, cls.doc_checked = cls.env["l10n_mx_edi.document"].create(
            [
                {
                    "datetime": fields.Datetime.now(),
                    "state": "invoice_received",
                    "move_id": cls.bill.id,
                    "sat_state": "valid",
                },
                {
                    "datetime": fields.Datetime.now(),
                    "state": "invoice_received",
                    "move_id": cls.bill.id,
                    "sat_state": "valid",
                    "sat_status_check_date": fields.Datetime.now(),
                },
            ]
        )
        cls.docs = cls.doc_unchecked + cls.doc_checked

    def _search_docs(self, from_cron=True):
        document_model = self.env["l10n_mx_edi.document"]
        domain = document_model._get_update_sat_status_domain(
            extra_domain=[("id", "in", self.docs.ids)],
            from_cron=from_cron,
        )
        return document_model.search(domain)

    def test_cron_domain_skips_recently_checked(self):
        self.assertEqual(self._search_docs(), self.doc_unchecked)

    def test_cron_domain_includes_stale_check(self):
        self.doc_checked.sat_status_check_date = fields.Datetime.now() - timedelta(
            hours=13
        )
        self.assertEqual(self._search_docs(), self.docs)

    def test_form_domain_not_affected(self):
        self.assertEqual(self._search_docs(from_cron=False), self.docs)

    def test_update_sat_state_stamps_check_date(self):
        # Without an attachment the upstream method returns early, before any
        # call to the SAT web service, but the document must still be stamped
        # so the cron sweep progresses.
        self.assertFalse(self.doc_unchecked.sat_status_check_date)
        self.doc_unchecked._update_sat_state()
        self.assertTrue(self.doc_unchecked.sat_status_check_date)
        self.assertFalse(self._search_docs())
