from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Clean up the data of 19.0 that 20.0 no longer uses.

    - The email template of the CFDI documents (noupdate): in 20.0 the payment
      receipt is sent with the native template of the payment or with the bank
      transaction template of this module.
    - The stored Fiscal Folio of the bank statement lines: in 20.0 the field
      comes from the move through _inherits.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    template = env.ref(
        "l10n_mx_edi_account_move_payment_report.mail_template_data_payment_receipt",
        raise_if_not_found=False,
    )
    if template:
        template.unlink()
    cr.execute(
        "ALTER TABLE account_bank_statement_line "
        "DROP COLUMN IF EXISTS l10n_mx_edi_cfdi_uuid"
    )
