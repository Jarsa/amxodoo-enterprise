# Copyright 2019, Jarsa Sistemas, S.A. de C.V.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lpgl.html).

{
    "name": "Payment Method on Statement Line",
    "summary": "Adds payment method to bank statement lines for use in CFDI payment complement",
    "version": "17.0.1.0.0",
    "category": "Report",
    "author": "Jarsa",
    "website": "https://www.jarsa.com",
    "license": "LGPL-3",
    "depends": [
        "account",
        "l10n_mx_edi",
    ],
    "data": [
        "views/account_bank_statement_line_view.xml",
    ],
    "installable": True,
}
