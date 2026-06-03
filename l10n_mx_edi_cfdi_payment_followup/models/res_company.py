from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_mx_edi_cfdi_payment_start_date = fields.Date(
        string="CFDI Payment Follow-up Start Date",
    )
    l10n_mx_edi_cfdi_responsible_team_id = fields.Many2one(
        comodel_name="mail.activity.team",
        string="CFDI Follow-up Responsible Team",
        help="Activity team that receives the CFDI complement follow-up "
        "activities (errors, replacements). Its members pick up the activities.",
    )

    def write(self, vals):
        start_date_changed = "l10n_mx_edi_cfdi_payment_start_date" in vals
        previous = (
            {c.id: c.l10n_mx_edi_cfdi_payment_start_date for c in self}
            if start_date_changed
            else {}
        )
        res = super().write(vals)
        if start_date_changed:
            AccountMove = self.env["account.move"]
            for company in self:
                new_date = company.l10n_mx_edi_cfdi_payment_start_date
                if not new_date or new_date == previous.get(company.id):
                    continue
                AccountMove._l10n_mx_edi_cfdi_recompute_for_company(company, new_date)
        return res
