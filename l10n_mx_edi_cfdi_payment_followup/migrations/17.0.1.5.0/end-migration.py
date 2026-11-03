from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Recompute the follow-up state of the payments in Error or Requested.

    Those states are kept by the compute, so they could hold stale values that
    the new rules resolve: an XML used to be validated (and set to Error) even
    when the move was out of scope, e.g. an invoice or a payment of a journal
    without follow-up, and a payment that already has its complement documents
    now becomes Validated (or Received) instead of keeping Error or Requested.

    This must be an ``end`` script for the same reason as the 17.0.1.4.1 one:
    the state depends on ``l10n_mx_edi_payment_policy``, which other modules
    loaded after this one extend.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    move_model = env["account.move"]
    moves = move_model.search(
        [("l10n_mx_edi_cfdi_payment_state", "in", ("error", "requested"))]
    )
    env.add_to_compute(move_model._fields["l10n_mx_edi_cfdi_payment_state"], moves)
    env.flush_all()
