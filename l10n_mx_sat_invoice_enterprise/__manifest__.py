# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Mexico - Invoices from SAT CFDIs (Enterprise)",
    "version": "19.0.1.1.0",
    "license": "AGPL-3",
    "category": "Accounting/Localizations",
    "summary": "Link the EDI document and validate the fiscal folio of the "
    "invoices created from SAT CFDIs",
    "author": "Jarsa, Odoo Mexican Association (AMOdoo)",
    "website": "https://github.com/amxodoo/enterprise",
    "depends": ["l10n_mx_sat_invoice", "l10n_mx_edi"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/l10n_mx_sat_statement_line_wizard_views.xml",
        "views/account_move_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_mx_sat_invoice_enterprise/static/src/bank_reconciliation/*",
        ],
        "web.assets_tests": [
            "l10n_mx_sat_invoice_enterprise/static/tests/tours/*",
        ],
    },
    "installable": True,
    "auto_install": True,
}
