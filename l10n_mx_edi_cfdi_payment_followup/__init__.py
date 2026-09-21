from . import models


def pre_init_hook(env):
    """Pre-create the CFDI payment state column with 'not_required' for every
    existing account.move so Odoo finds the column already populated when it
    registers the stored compute field, and therefore does NOT queue a
    recompute over the whole history. Users opt-in by setting the start date
    in Accounting > Settings, which triggers a bounded recompute for moves
    from that date onwards (see res_company.write).

    The value is set through the column DEFAULT instead of an UPDATE: since
    PostgreSQL 11 that is a metadata-only change, while an UPDATE rewrites
    every row of account_move and leaves a dead copy of the table behind
    (one per install attempt when the install is retried).
    """
    env.cr.execute(
        """
        ALTER TABLE account_move
        ADD COLUMN IF NOT EXISTS l10n_mx_edi_cfdi_payment_state VARCHAR
            DEFAULT 'not_required',
        ADD COLUMN IF NOT EXISTS l10n_mx_edi_cfdi_is_supplier_payment BOOLEAN
            DEFAULT false
        """
    )
