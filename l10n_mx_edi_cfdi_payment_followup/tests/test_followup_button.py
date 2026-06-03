from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .. import pre_init_hook
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
        """Activity is assigned to the configured responsible team."""
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
        self.assertEqual(activities[0].team_id, self.responsible_team)
        self.assertEqual(
            activities[0].activity_type_id,
            self.env.ref(
                "l10n_mx_edi_cfdi_payment_followup."
                "mail_activity_type_cfdi_complement"
            ),
        )

    def test_pre_init_hook_initializes_state_without_compute(self):
        """pre_init_hook pre-fills the column with 'not_required' so Odoo does
        not queue a recompute over historical data when the stored compute
        field is registered.
        """
        AccountMove = self.env["account.move"]
        # Wipe the column to simulate the state right before the module is
        # installed for the first time.
        self.env.cr.execute(
            "UPDATE account_move SET l10n_mx_edi_cfdi_payment_state = NULL "
            "WHERE id = %s",
            [self.payment.move_id.id],
        )
        AccountMove.invalidate_model(["l10n_mx_edi_cfdi_payment_state"])

        pre_init_hook(self.env)

        self.env.cr.execute(
            "SELECT l10n_mx_edi_cfdi_payment_state FROM account_move WHERE id = %s",
            [self.payment.move_id.id],
        )
        self.assertEqual(self.env.cr.fetchone()[0], "not_required")

    def test_set_start_date_recomputes_in_range(self):
        """Setting start_date on the company triggers a bounded recompute
        for moves from that date onwards.
        """
        # Disable feature: simulates the state right after a fresh install
        self.company_mx.l10n_mx_edi_cfdi_payment_start_date = False
        self.env.flush_all()
        self.payment.move_id.write({"l10n_mx_edi_cfdi_payment_state": "not_required"})
        # Enabling the feature should recompute the reconciled PPD payment
        self.company_mx.l10n_mx_edi_cfdi_payment_start_date = "2020-01-01"
        self.env.flush_all()
        self.assertIn(
            self.payment.move_id.l10n_mx_edi_cfdi_payment_state,
            ("pending", "validated", "error", "requested"),
        )
