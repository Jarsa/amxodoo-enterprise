from datetime import timedelta

from odoo import api, fields, models

# The upstream domain matches every received CFDI of a posted move forever, so
# with more than `batch_size` (100) of them the cron re-triggers itself
# endlessly, keeps `ir_cron` row-locked and blocks module install/upgrade.
# Re-checking each received document at most once per window keeps the queue
# draining while the daily cron still refreshes every document.
SAT_RECHECK_HOURS = 12


class L10nMxEdiDocument(models.Model):
    _inherit = "l10n_mx_edi.document"

    sat_status_check_date = fields.Datetime(
        string="Last SAT Status Check",
        copy=False,
        help="Last time the SAT status of this document was fetched. "
        "The SAT update cron skips received documents checked recently "
        "to avoid re-processing the same batch in a loop.",
    )

    @api.model
    def _get_update_sat_status_domains(self, from_cron=True):
        domains = super()._get_update_sat_status_domains(from_cron=from_cron)
        if from_cron:
            limit_date = fields.Datetime.now() - timedelta(hours=SAT_RECHECK_HOURS)
            for domain in domains:
                if ("state", "=", "invoice_received") in domain:
                    domain.extend(
                        [
                            "|",
                            ("sat_status_check_date", "=", False),
                            ("sat_status_check_date", "<", limit_date),
                        ]
                    )
        return domains

    def _update_sat_state(self):
        # Stamp before super() so even documents that exit early (e.g. without
        # a decodable attachment) leave the cron queue and the sweep progresses.
        self.sat_status_check_date = fields.Datetime.now()
        return super()._update_sat_state()
