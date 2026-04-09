# Copyright 2019, Jarsa Sistemas, S.A. de C.V.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    @api.model_create_multi
    def create(self, vals_list):
        payment_methods = [
            vals.pop("l10n_mx_edi_payment_method_id", None) for vals in vals_list
        ]
        records = super().create(vals_list)
        for record, payment_method in zip(records, payment_methods, strict=False):
            if payment_method:
                record.move_id.write({"l10n_mx_edi_payment_method_id": payment_method})
        return records
