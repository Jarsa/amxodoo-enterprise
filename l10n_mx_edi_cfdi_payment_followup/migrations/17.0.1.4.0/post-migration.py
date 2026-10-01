from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Recompute the follow-up state of the payments in scope.

    The payment policy of a vendor bill now comes from its CFDI instead of the
    computed field, so the stored states of existing payments may be outdated.
    Only entries of follow-up journals from each company's start date are
    recomputed: any other move is Not Required whatever the policy is, and
    rewriting those rows would only bloat ``account_move``.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    move_model = env["account.move"]
    companies = env["res.company"].search(
        [("l10n_mx_edi_cfdi_payment_start_date", "!=", False)]
    )
    for company in companies:
        moves = move_model.search(
            [
                ("company_id", "=", company.id),
                ("move_type", "=", "entry"),
                ("date", ">=", company.l10n_mx_edi_cfdi_payment_start_date),
                ("journal_id.l10n_mx_edi_cfdi_payment_followup", "=", True),
            ]
        )
        env.add_to_compute(move_model._fields["l10n_mx_edi_cfdi_payment_state"], moves)
    env.flush_all()
