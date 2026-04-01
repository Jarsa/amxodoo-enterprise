from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .. import post_init_hook
from .common import TestCfdiPaymentFollowupCommon


@tagged("post_install", "-at_install")
class TestFollowupButton(TestCfdiPaymentFollowupCommon):
    def setUp(self):
        super().setUp()
        self.payment.move_id.write(
            {
                "l10n_mx_edi_cfdi_uuid": False,
                "l10n_mx_edi_cfdi_payment_state": "pending",
            }
        )

    def test_button_sends_email(self):
        """Button creates an outgoing mail.mail record."""
        before_count = self.env["mail.mail"].search_count([])
        self.payment.move_id.action_request_cfdi_complement()
        after_count = self.env["mail.mail"].search_count([])
        self.assertGreater(after_count, before_count)

    def test_button_sets_requested(self):
        """State transitions to 'requested' after button click."""
        self.payment.move_id.action_request_cfdi_complement()
        self.assertEqual(
            self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "requested"
        )

    def test_button_updates_followup_date(self):
        """last_followup_date is set to approximately now after button click."""
        before = fields.Datetime.now()
        self.payment.move_id.action_request_cfdi_complement()
        after = fields.Datetime.now()
        followup_date = self.payment.move_id.l10n_mx_edi_cfdi_payment_last_followup_date
        self.assertTrue(followup_date)
        self.assertGreaterEqual(followup_date, before)
        self.assertLessEqual(followup_date, after)

    def test_button_noop_on_validated(self):
        """State 'validated' → button does nothing (guard condition)."""
        self.payment.move_id.write({"l10n_mx_edi_cfdi_payment_state": "validated"})
        before_count = self.env["mail.mail"].search_count([])
        self.payment.move_id.action_request_cfdi_complement()
        after_count = self.env["mail.mail"].search_count([])
        self.assertEqual(before_count, after_count)
        self.assertEqual(
            self.payment.move_id.l10n_mx_edi_cfdi_payment_state, "validated"
        )

    def test_button_uses_tagged_contact(self):
        """Contact with 'cfdi_complement_contact' tag is used as recipient."""
        # Create the category tag
        tag = self.env["res.partner.category"].create(
            {"name": "cfdi_complement_contact"}
        )
        # Create a child contact with that tag
        self.env["res.partner"].create(
            {
                "name": "CFDI Contact",
                "email": "cfdi@vendor.mx",
                "parent_id": self.customer.id,
                "category_id": [(4, tag.id)],
            }
        )
        self.payment.move_id.action_request_cfdi_complement()
        # Check that the sent mail targets the tagged contact email
        last_mail = self.env["mail.mail"].search([], order="id desc", limit=1)
        self.assertIn("cfdi@vendor.mx", last_mail.email_to or "")

    def test_button_fallback_email(self):
        """No tagged contact → uses partner main email."""
        self.payment.move_id.action_request_cfdi_complement()
        last_mail = self.env["mail.mail"].search([], order="id desc", limit=1)
        self.assertIn(self.customer.email, last_mail.email_to or "")

    def test_cron_resends_after_interval(self):
        """action_cfdi_payment_followup re-sends after N days."""
        self.payment.move_id.action_request_cfdi_complement()
        # Simulate the last followup was 6 days ago (> default 5-day interval)
        old_date = fields.Datetime.now() - timedelta(days=6)
        self.payment.move_id.write(
            {"l10n_mx_edi_cfdi_payment_last_followup_date": old_date}
        )
        before_count = self.env["mail.mail"].search_count([])
        self.env["account.move"].action_cfdi_payment_followup()
        after_count = self.env["mail.mail"].search_count([])
        self.assertGreater(after_count, before_count)

    def test_cron_skips_recent(self):
        """Record requested 1 day ago → not resent by cron (within interval)."""
        self.payment.move_id.action_request_cfdi_complement()
        # Simulate the last followup was 1 day ago (< default 5-day interval)
        recent_date = fields.Datetime.now() - timedelta(days=1)
        self.payment.move_id.write(
            {"l10n_mx_edi_cfdi_payment_last_followup_date": recent_date}
        )
        before_count = self.env["mail.mail"].search_count([])
        self.env["account.move"].action_cfdi_payment_followup()
        after_count = self.env["mail.mail"].search_count([])
        self.assertEqual(before_count, after_count)

    def test_cron_respects_start_date(self):
        """Record with payment date before start date → not processed by cron."""
        # Set start date to tomorrow
        tomorrow = fields.Date.today() + timedelta(days=1)
        self.company_mx.l10n_mx_edi_cfdi_payment_start_date = tomorrow
        try:
            self.payment.move_id.write(
                {
                    "l10n_mx_edi_cfdi_payment_state": "requested",
                    "l10n_mx_edi_cfdi_payment_last_followup_date": fields.Datetime.now()
                    - timedelta(days=10),
                }
            )
            before_count = self.env["mail.mail"].search_count([])
            self.env["account.move"].action_cfdi_payment_followup()
            after_count = self.env["mail.mail"].search_count([])
            self.assertEqual(before_count, after_count)
        finally:
            self.company_mx.l10n_mx_edi_cfdi_payment_start_date = "2020-01-01"

    def test_activity_created_on_error(self):
        """Failed XML validation creates a mail.activity."""

        # Build XML with wrong forma_pago to trigger error
        xml = self._build_cfdi_xml(
            payment_uuid="PAY-UUID-ERR-0001",
            payment_date=fields.Date.today(),
            amount=5000.0,
            invoice_uuids=[self.invoice_uuid],
            forma_pago="01",
        )
        self._attach_xml(self.payment.move_id, xml)
        activities = self.payment.move_id.activity_ids
        self.assertTrue(activities)
        self.assertTrue(activities[0].summary)

    def test_activity_assigned_to_responsible(self):
        """Activity is assigned to the configured responsible user."""
        xml = self._build_cfdi_xml(
            payment_uuid="PAY-UUID-ERR-0002",
            payment_date=fields.Date.today(),
            amount=5000.0,
            invoice_uuids=[self.invoice_uuid],
            forma_pago="01",
        )
        self._attach_xml(self.payment.move_id, xml)
        activities = self.payment.move_id.activity_ids
        self.assertTrue(activities)
        self.assertEqual(activities[0].user_id, self.responsible_user)

    def test_post_init_hook_sets_start_date(self):
        """post_init_hook sets start_date for companies without it."""
        from datetime import date

        # Create a new company with no start_date
        new_company = self.env["res.company"].create(
            {
                "name": "New Company No StartDate",
                "country_id": self.env.ref("base.mx").id,
                "currency_id": self.mxn.id,
            }
        )
        # Ensure field is not set
        new_company.l10n_mx_edi_cfdi_payment_start_date = False

        post_init_hook(self.env)

        self.assertEqual(new_company.l10n_mx_edi_cfdi_payment_start_date, date.today())
