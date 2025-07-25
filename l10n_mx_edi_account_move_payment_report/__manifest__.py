# Copyright 2019, Jarsa Sistemas, S.A. de C.V.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lpgl.html).

{
    "name": "Payment Receipt on Invoice",
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
        "report/report_payment_receipt_invoice.xml",
        "views/report_action.xml",
    ],
    "installable": True,
}