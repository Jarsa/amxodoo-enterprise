from odoo import models

DISABLE_PARAM = "l10n_mx_edi_sale_cfdi_to_public_manual.disable"


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # No `api.depends` on purpose: Odoo unions the dependencies of every
    # `_compute_l10n_mx_edi_cfdi_to_public` in the MRO, so the upstream triggers
    # (customer, company) still fire and this override only decides the value.
    def _compute_l10n_mx_edi_cfdi_to_public(self):
        # Restore the pre-17.4 behaviour: upstream ticks the box whenever the
        # customer has no complete fiscal address (country, zip and VAT), which
        # is also the case while the order has no customer yet. Invoicing to
        # "PUBLICO EN GENERAL" by mistake forces a cancel and a re-stamp, so the
        # box is left to the user: new orders start unticked and a manual tick
        # is kept when the customer changes.
        disabled = self.env["ir.config_parameter"].sudo().get_param(DISABLE_PARAM, "")
        if disabled.strip().lower() in ("1", "true", "yes"):
            # Kill switch: give the standard Odoo behaviour back without
            # uninstalling the module.
            return super()._compute_l10n_mx_edi_cfdi_to_public()
        for order in self:
            order.l10n_mx_edi_cfdi_to_public = order.l10n_mx_edi_cfdi_to_public
