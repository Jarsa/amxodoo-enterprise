import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

CFDI_XSLT_CADENA = "l10n_mx_edi_40/data/4.0/cadenaoriginal_4_0.xslt"
CFDI_XSLT_CADENA_TFD = "l10n_mx_edi_40/data/4.0/cadenaoriginal_TFD_1_1.xslt"


class HrPayslipLine(models.Model):
    _inherit = "hr.payslip.line"
    _description = "Payslip Line"

    reporting_category = fields.Selection(
        related="salary_rule_id.reporting_category", readonly=False
    )

    rule_type = fields.Selection(
        [
            ("alw", "Allowance"),
            ("ded", "Deduction"),
            ("total", "Total"),
            ("company", "Company"),
            ("na", "NA"),
        ],
        compute="_compute_rule_type",
    )
    hide_rule = fields.Boolean()

    @api.depends("category_id")
    def _compute_rule_type(self):
        for payslip in self:
            if payslip.category_id.code == "ALW":
                payslip.rule_type = "alw"
            elif payslip.category_id.code == "DED":
                payslip.rule_type = "ded"
            elif payslip.category_id.code == "NET":
                payslip.rule_type = "total"
            elif payslip.category_id.code in ("IMSS_C", "ISN"):
                payslip.rule_type = "company"
            else:
                payslip.rule_type = "na"
