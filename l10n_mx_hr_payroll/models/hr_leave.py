import datetime
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HrWorkEntry(models.Model):
    _inherit = "hr.work.entry"

    hr_leave_id = fields.Many2one("hr.leave")


class HolidaysType(models.Model):
    _inherit = "hr.leave"

    disability_folio = fields.Char()
    is_disability = fields.Boolean(compute="_compute_is_disability")

    @api.depends("holiday_status_id")
    def _compute_is_disability(self):
        for disability in self:
            if disability.holiday_status_id.disabilities_type:
                disability.is_disability = True
            else:
                disability.is_disability = False

    def _get_number_of_days(self, date_from, date_to, employee_id):
        res = super()._get_number_of_days(date_from, date_to, employee_id)
        for holiday in self:
            if (
                holiday.date_to
                and holiday.date_from
                and holiday.holiday_status_id.disabilities_type
            ):
                holiday.number_of_days = float(
                    (
                        holiday.date_to - holiday.date_from + datetime.timedelta(days=1)
                    ).days
                )
        return res
