{
    "name": "Mexico - CFDI Payment Complement Follow-up",
    "summary": "Track and validate CFDI payment complements for PPD invoices",
    "version": "17.0.1.0.0",
    "author": "Jarsa",
    "website": "https://github.com/amxodoo/enterprise",
    "license": "LGPL-3",
    "category": "Accounting/Localizations/Mexico",
    "depends": [
        "account_accountant",
        "l10n_mx_edi",
    ],
    "data": [
        "security/l10n_mx_edi_cfdi_payment_followup_security.xml",
        "security/ir.model.access.csv",
        "data/mail_template_data.xml",
        "data/ir_cron_data.xml",
        "views/res_config_settings_views.xml",
        "views/account_move_views.xml",
        "views/account_payment_views.xml",
        "views/account_bank_statement_line_views.xml",
    ],
    "post_init_hook": "post_init_hook",
}
