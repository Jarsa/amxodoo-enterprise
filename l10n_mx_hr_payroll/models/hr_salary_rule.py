from odoo import fields, models


class HrSalaryRule(models.Model):
    _inherit = "hr.salary.rule"
    _description = "Salary Rule"

    reporting_category = fields.Selection(
        [
            ("basic", "BASIC"),
            ("gross", "GROSS"),
            ("net", "NET"),
        ]
    )

    rule_type_cfdi = fields.Selection(
        [
            ("na", "N/A"),
            ("alw", "Allowance"),
            ("ded", "Deduction"),
            ("otp", "Other Payment"),
        ],
        string="Rule Type",
        default="na",
    )
    hide_rule = fields.Boolean(string="Hide rule")
    category_code = fields.Char("Category Code", related="category_id.code", store=True)
    allowance_type_l10n_mx = fields.Many2one(
        "payroll.allowance",
        string="Allowance Type (cfdi)",
        help="Allowance Type for Mexico.",
    )
    deduction_type_l10n_mx = fields.Many2one(
        "payroll.deduction",
        string="Deduction Type (cfdi)",
        help="Deduction Type for Mexico.",
    )
    otherpayment_type_l10n_mx = fields.Many2one(
        "payroll.otherpayment",
        string="Otros Pagos (cfdi)",
        help="Other Payments Type for Mexico.",
    )
    payment_method_l10n_mx = fields.Selection(
        selection=[
            ("001", "Cash"),
            ("002", "Species"),
        ],
        string="Payment Method",
        default="001",
    )
    exemption = fields.Boolean("Allowance with exemption for ISR")
    integer_income = fields.Selection(
        selection=[
            ("001", "Ordinary"),
            ("002", "Monthly extraordinary"),
            ("003", "Annual extraordinary"),
            ("004", "Exempt part per day"),
        ],
        string="Integer for income like allowance",
    )
    #    monto_exencion = fields.Float('Exención (UMA)', digits = (12,3))
    variable_imss = fields.Boolean("Percepción variable para el IMSS")
    type_variable_imss = fields.Selection(
        selection=[
            ("001", "Entire amount"),
            ("002", "Excess over (% de UMA)"),
            ("003", "Excess over (% de SBC)"),
        ],
        string="Type",
        default="001",
    )
    amount_variable_imss = fields.Float("Monto")
    integer_ptu = fields.Boolean("Integer for PTU")
    integer_state = fields.Boolean("Integer for state TAX")
    taxable_part = fields.Many2one("hr.salary.rule")
    exempt_part = fields.Many2one("hr.salary.rule")
    cuenta_especie = fields.Many2one(
        "account.account", "Cuenta de pago", domain=[("deprecated", "=", False)]
    )
    fondo_ahorro_aux = fields.Boolean("Fondo de ahorro")
