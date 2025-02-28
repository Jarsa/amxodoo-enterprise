from odoo import models


class HrPayrollCustomReport(models.Model):
    _inherit = "hr.payroll.report"

    def _from(self, additional_rules):
        from_str = """
            FROM
                (SELECT * FROM hr_payslip WHERE state IN ('done', 'paid')) p
                left join hr_employee e on (p.employee_id = e.id)
                left join hr_payslip_worked_days wd on (wd.payslip_id = p.id)
                left join hr_work_entry_type wet on (wet.id = wd.work_entry_type_id)
                left join (select payslip_id, min(id) as min_line from hr_payslip_worked_days group by payslip_id) min_id on (min_id.payslip_id = p.id)
                left join hr_payslip_line pln on (pln.slip_id = p.id)
                left join hr_payslip_line plb on (plb.slip_id = p.id)
                left join hr_payslip_line plg on (plg.slip_id = p.id)
                left join hr_contract c on (p.contract_id = c.id)
                left join hr_department d on (e.department_id = d.id)
                left join hr_salary_rule srn on (pln.salary_rule_id = srn.id)
                left join hr_salary_rule srb on (plb.salary_rule_id = srb.id)
                left join hr_salary_rule srg on (plg.salary_rule_id = srg.id)
        """

        # Add the reporting_category condition for each joined salary_rule
        from_str += """
            WHERE TRUE
            AND (pln.code = 'NET' OR srn.reporting_category = 'net')
            AND (plb.code = 'BASIC' OR srb.reporting_category = 'basic')
            AND (plg.code = 'GROSS' OR srg.reporting_category = 'gross')
        """

        handled_fields = []
        for rule in additional_rules:
            field_name = rule._get_report_field_name()
            if field_name in handled_fields:
                continue
            handled_fields.append(field_name)
            from_str += """
                left join hr_payslip_line "%s" on ("%s".slip_id = p.id and "%s".code = '%s')""" % (
                field_name,
                field_name,
                field_name,
                rule.code,
            )

        return from_str
