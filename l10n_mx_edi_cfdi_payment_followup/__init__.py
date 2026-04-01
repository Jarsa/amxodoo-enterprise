from . import models


def post_init_hook(env):
    from datetime import date

    today = date.today()
    for company in env["res.company"].search([]):
        if not company.l10n_mx_edi_cfdi_payment_start_date:
            company.l10n_mx_edi_cfdi_payment_start_date = today
