from werkzeug.urls import url_quote_plus

from odoo import models
from odoo.addons.base.models.ir_qweb import keep_query

class L10nMxEdiDocument(models.Model):
    _name = "l10n_mx_edi.document"
    _inherit = ["l10n_mx_edi.document", "mail.thread"]

    def action_print_payment(self):
        return self.env.ref("l10n_mx_edi_account_move_payment_report.report_payment_receipt_invoice").sudo().report_action(self)

    def _l10n_mx_edi_get_extra_common_report_values(self):
        self.ensure_one()
        cfdi_infos = self.env["l10n_mx_edi.document"]._decode_cfdi_attachment(self.attachment_id.raw)
        if not cfdi_infos:
            return {}

        barcode_value_params = keep_query(
            id=cfdi_infos["uuid"],
            re=cfdi_infos["supplier_rfc"],
            rr=cfdi_infos["customer_rfc"],
            tt=cfdi_infos["amount_total"],
        )
        barcode_sello = url_quote_plus(cfdi_infos["sello"][-8:], safe="=/").replace("%2B", "+")
        barcode_value = url_quote_plus(f"https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?{barcode_value_params}&fe={barcode_sello}")
        barcode_src = f"/report/barcode/?barcode_type=QR&value={barcode_value}&width=180&height=180"

        return {
            **cfdi_infos,
            "barcode_src": barcode_src,
        }

    def _l10n_mx_edi_get_extra_payment_report_values(self):
        """ Collect extra values used to render the payment PDF report containing CFDI information.

        :return: A python dictionary.
        """
        self.ensure_one()
        cfdi_infos = self._l10n_mx_edi_get_extra_common_report_values()
        if not cfdi_infos:
            return cfdi_infos

        node = cfdi_infos["cfdi_node"].xpath("//*[local-name()='Pago']")[0]
        payment_info = cfdi_infos["payment_info"] = {}
        payment_info["from_account_vat"] = node.get("RfcEmisorCtaOrd")
        payment_info["from_account_name"] = node.get("NomBancoOrdExt")
        payment_info["from_account_number"] = node.get("CtaOrdenante")
        payment_info["to_account_vat"] = node.get("RfcEmisorCtaBen")
        payment_info["to_account_number"] = node.get("CtaBeneficiario")

        related_invoices = cfdi_infos["invoices"] = []
        uuids = []
        for node in cfdi_infos["cfdi_node"].xpath("//*[local-name()='DoctoRelacionado']"):
            uuids.append(node.attrib["IdDocumento"])
            related_invoices.append({
                "uuid": node.attrib["IdDocumento"],
                "partiality": node.attrib["NumParcialidad"],
                "previous_balance": float(node.attrib["ImpSaldoAnt"]),
                "amount_paid": float(node.attrib["ImpPagado"]),
                "balance": float(node.attrib["ImpSaldoInsoluto"]),
                "currency": node.attrib["MonedaDR"],
            })
        invoices = self.env["account.move"].search([("l10n_mx_edi_cfdi_uuid", "in", uuids)])
        invoices_map = {x.l10n_mx_edi_cfdi_uuid: x for x in invoices}
        for invoice_values in related_invoices:
            invoice_values["invoice"] = invoices_map.get(invoice_values["uuid"], self.env["account.move"])

        return cfdi_infos

    def _process_attachments_for_template_post(self, mail_template):
        """ Add CFDI attachment to template. """
        result = super()._process_attachments_for_template_post(mail_template)
        for rec in self.filtered("attachment_id"):
            rec_result = result.setdefault(rec.id, {})
            rec_result.setdefault("attachment_ids", []).append(rec.attachment_id.id)
        return result
