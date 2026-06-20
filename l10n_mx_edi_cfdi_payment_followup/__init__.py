from . import models


def pre_init_hook(env):
    """Pre-create the CFDI payment state column with 'not_required' for every
    existing account.move so Odoo finds the column already populated when it
    registers the stored compute field, and therefore does NOT queue a
    recompute over the whole history. Users opt-in by setting the start date
    in Accounting > Settings, which triggers a bounded recompute for moves
    from that date onwards (see res_company.write).
    """
    env.cr.execute(
        """
        ALTER TABLE account_move
        ADD COLUMN IF NOT EXISTS l10n_mx_edi_cfdi_payment_state VARCHAR
        """
    )
    env.cr.execute(
        """
        UPDATE account_move
        SET l10n_mx_edi_cfdi_payment_state = 'not_required'
        WHERE l10n_mx_edi_cfdi_payment_state IS NULL
        """
    )
    env.cr.execute(
        """
        ALTER TABLE account_move
        ADD COLUMN IF NOT EXISTS l10n_mx_edi_cfdi_is_supplier_payment BOOLEAN
        """
    )
    env.cr.execute(
        """
        UPDATE account_move
        SET l10n_mx_edi_cfdi_is_supplier_payment = false
        WHERE l10n_mx_edi_cfdi_is_supplier_payment IS NULL
        """
    )
