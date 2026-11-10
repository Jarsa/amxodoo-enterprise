# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Link the existing invoices to the downloaded CFDI of their fiscal folio."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["account.move"].search(
        [
            ("l10n_mx_edi_cfdi_uuid", "!=", False),
            ("l10n_mx_sat_document_id", "=", False),
            ("state", "!=", "cancel"),
        ]
    )._l10n_mx_sat_link_by_fiscal_folio()
