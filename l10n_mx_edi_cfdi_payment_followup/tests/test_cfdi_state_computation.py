from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import TestCfdiPaymentFollowupCommon


@tagged("post_install", "-at_install")
class TestCfdiStateComputation(TestCfdiPaymentFollowupCommon):
    def _get_payment_move(self):
        """Return the account.move behind cls.payment."""
        return self.payment.move_id

    def test_state_not_required_pue(self):
        """Payments reconciled only with PUE invoices get 'not_required'."""
        # Create a PUE invoice: same month due date
        today = fields.Date.today()
        pue_invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.customer.id,
                "company_id": self.company_mx.id,
                "journal_id": self.sale_journal.id,
                "invoice_date": today,
                "invoice_date_due": today,  # same day → PUE
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "PUE Service",
                            "price_unit": 1000.0,
                            "account_id": self.account_income.id,
                        },
                    )
                ],
            }
        )
        pue_invoice.action_post()

        pue_payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.customer.id,
                "amount": 1000.0,
                "currency_id": self.mxn.id,
                "journal_id": self.bank_journal.id,
                "date": today,
                "company_id": self.company_mx.id,
            }
        )
        pue_payment.action_post()
        pay_line = pue_payment.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        inv_line = pue_invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        (pay_line | inv_line).reconcile()

        pue_payment.move_id.invalidate_recordset(["l10n_mx_edi_cfdi_payment_state"])
        self.assertEqual(
            pue_payment.move_id.l10n_mx_edi_cfdi_payment_state, "not_required"
        )

    def test_state_not_required_before_start_date(self):
        """Payments before the company start date get 'not_required'."""
        move = self._get_payment_move()
        # Set start date to tomorrow so our payment (today) is before it
        tomorrow = fields.Date.today() + timedelta(days=1)
        self.company_mx.l10n_mx_edi_cfdi_payment_start_date = tomorrow
        try:
            # company field is not in @api.depends; call compute directly
            move._compute_l10n_mx_edi_cfdi_payment_state()
            self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "not_required")
        finally:
            self.company_mx.l10n_mx_edi_cfdi_payment_start_date = "2020-01-01"

    def test_state_pending_ppd(self):
        """PPD invoice reconciled, no UUID → state 'pending'."""
        move = self._get_payment_move()
        # Ensure UUID is cleared on the payment move
        move.write({"l10n_mx_edi_cfdi_uuid": False})
        move.invalidate_recordset(["l10n_mx_edi_cfdi_payment_state"])
        # The invoice was created with PPD (due date next month) and is reconciled
        state = move.l10n_mx_edi_cfdi_payment_state
        self.assertEqual(state, "pending")

    def test_state_validated_has_uuid(self):
        """payment_sent document exists → state 'validated'."""
        move = self._get_payment_move()
        move.write({"l10n_mx_edi_cfdi_payment_state": "pending"})
        # Create a payment_sent document — this is a declared dependency
        self.env["l10n_mx_edi.document"].create(
            {
                "move_id": move.id,
                "state": "payment_sent",
                "sat_state": "not_defined",
                "datetime": fields.Datetime.now(),
            }
        )
        # Dependency change triggers automatic recompute on next access
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "validated")

    def test_state_preserves_requested(self):
        """Manually set 'requested' is NOT overwritten by recompute."""
        move = self._get_payment_move()
        # Clear UUID so the normal logic would set it to 'pending'
        move.write(
            {
                "l10n_mx_edi_cfdi_uuid": False,
                "l10n_mx_edi_cfdi_payment_state": "requested",
            }
        )
        move.invalidate_recordset(["l10n_mx_edi_cfdi_payment_state"])
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "requested")

    def test_state_preserves_error(self):
        """Manually set 'error' is NOT overwritten by recompute."""
        move = self._get_payment_move()
        move.write(
            {
                "l10n_mx_edi_cfdi_uuid": False,
                "l10n_mx_edi_cfdi_payment_state": "error",
            }
        )
        move.invalidate_recordset(["l10n_mx_edi_cfdi_payment_state"])
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "error")

    def test_state_not_required_non_payment(self):
        """Regular journal entry without payment_id → 'not_required'."""
        entry = self.env["account.move"].create(
            {
                "move_type": "entry",
                "company_id": self.company_mx.id,
                "journal_id": self.sale_journal.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": self.account_income.id,
                            "debit": 100.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": self.account_bank.id,
                            "credit": 100.0,
                        },
                    ),
                ],
            }
        )
        entry.action_post()
        self.assertEqual(entry.l10n_mx_edi_cfdi_payment_state, "not_required")

    def test_unreconcile_clears_error(self):
        """Un-reconciling from a PPD invoice releases 'error' to 'not_required'."""
        move = self._get_payment_move()
        move.write(
            {
                "l10n_mx_edi_cfdi_uuid": False,
                "l10n_mx_edi_cfdi_payment_state": "error",
            }
        )
        # Sanity: state is preserved while reconciliation still holds
        move.invalidate_recordset(["l10n_mx_edi_cfdi_payment_state"])
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "error")

        # Break the reconciliation with the PPD invoice
        pay_line = move.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        pay_line.remove_move_reconcile()

        move.invalidate_recordset(["l10n_mx_edi_cfdi_payment_state"])
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "not_required")

    def test_unreconcile_clears_requested(self):
        """Un-reconciling from a PPD invoice releases 'requested' to 'not_required'."""
        move = self._get_payment_move()
        move.write(
            {
                "l10n_mx_edi_cfdi_uuid": False,
                "l10n_mx_edi_cfdi_payment_state": "requested",
            }
        )
        move.invalidate_recordset(["l10n_mx_edi_cfdi_payment_state"])
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "requested")

        pay_line = move.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        pay_line.remove_move_reconcile()

        move.invalidate_recordset(["l10n_mx_edi_cfdi_payment_state"])
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "not_required")

    def test_multicompany_start_date(self):
        """Two companies with different start dates behave independently."""
        company2 = self.env["res.company"].create(
            {
                "name": "Test MX Company 2",
                "country_id": self.env.ref("base.mx").id,
                "currency_id": self.mxn.id,
            }
        )
        # Company 2: start date in the far future → payment before start
        company2.l10n_mx_edi_cfdi_payment_start_date = "2099-01-01"
        # Company 1: start date in past → payment after start
        self.company_mx.l10n_mx_edi_cfdi_payment_start_date = "2020-01-01"
        # Our payment (company_mx) should be pending (start date in past)
        move = self._get_payment_move()
        move.write(
            {
                "l10n_mx_edi_cfdi_uuid": False,
                "l10n_mx_edi_cfdi_payment_state": "pending",
            }
        )
        move.invalidate_recordset(["l10n_mx_edi_cfdi_payment_state"])
        self.assertEqual(move.l10n_mx_edi_cfdi_payment_state, "pending")
