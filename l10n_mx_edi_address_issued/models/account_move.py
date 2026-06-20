from odoo import _, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_mx_edi_payment_issued_address(self, pay_results):
        """Branch issued address (res.partner) for the payment complement.

        It is taken from the ``l10n_mx_address_issued_id`` of the journal of the
        reconciled invoices. ``l10n_mx_edi_extended`` already uses that same
        address as the invoice ``DomicilioFiscalReceptor`` for foreign/generic
        customers, so deriving ``LugarExpedicion`` from here makes both nodes
        match and satisfies CFDI40149.

        :return: tuple ``(issued_address, error)``. ``issued_address`` may be an
            empty recordset when no journal defines a branch address.
        """
        addresses = {
            inv["invoice"].journal_id.l10n_mx_address_issued_id
            for inv in pay_results["invoice_results"]
            if inv["invoice"].journal_id.l10n_mx_address_issued_id
        }
        if len(addresses) > 1:
            return self.env["res.partner"], _(
                "Cannot stamp a payment complement reconciling invoices from "
                "different branches (LugarExpedicion). Register one payment per "
                "branch."
            )
        return (next(iter(addresses)) if addresses else self.env["res.partner"]), None

    def _l10n_mx_edi_add_payment_cfdi_values(self, cfdi_values, pay_results):
        # EXTENDS 'l10n_mx_edi'
        # Set the branch issued address before super() so that both
        # 'lugar_expedicion' (= issued_address.zip) and the 'fecha' timezone
        # (taken from issued_address) use the branch instead of the company HQ.
        issued_address, error = self._l10n_mx_edi_payment_issued_address(pay_results)
        if error:
            cfdi_values["errors"] = [error]
            return
        if issued_address:
            cfdi_values["issued_address"] = issued_address
        super()._l10n_mx_edi_add_payment_cfdi_values(cfdi_values, pay_results)
