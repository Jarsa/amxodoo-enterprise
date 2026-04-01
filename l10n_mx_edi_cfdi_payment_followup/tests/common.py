from datetime import date

from lxml import etree

from odoo import fields
from odoo.tests.common import TransactionCase


def _first_day_next_month(d=None):
    """Return the first day of the month following d (default: today)."""
    d = d or date.today()
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


class TestCfdiPaymentFollowupCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ---- Company (Mexico, MXN) ----------------------------------------
        cls.mxn = cls.env.ref("base.MXN")
        cls.company_mx = cls.env["res.company"].create(
            {
                "name": "Test MX Company",
                "country_id": cls.env.ref("base.mx").id,
                "currency_id": cls.mxn.id,
            }
        )
        cls.env.ref("base.user_admin").sudo().write(
            {"company_ids": [(4, cls.company_mx.id)]}
        )
        cls.env = cls.env(
            user=cls.env.ref("base.user_admin"),
            context=dict(cls.env.context, allowed_company_ids=[cls.company_mx.id]),
        )

        # ---- Accounts -------------------------------------------------------
        cls.account_receivable = cls.env["account.account"].create(
            {
                "name": "Receivable Test",
                "code": "TEST.REC",
                "account_type": "asset_receivable",
                "company_id": cls.company_mx.id,
                "reconcile": True,
            }
        )
        cls.account_payable = cls.env["account.account"].create(
            {
                "name": "Payable Test",
                "code": "TEST.PAY",
                "account_type": "liability_payable",
                "company_id": cls.company_mx.id,
                "reconcile": True,
            }
        )
        cls.account_income = cls.env["account.account"].create(
            {
                "name": "Income Test",
                "code": "TEST.INC",
                "account_type": "income",
                "company_id": cls.company_mx.id,
            }
        )
        cls.account_bank = cls.env["account.account"].create(
            {
                "name": "Bank Test",
                "code": "TEST.BNK",
                "account_type": "asset_cash",
                "company_id": cls.company_mx.id,
            }
        )
        cls.account_outstanding_receipts = cls.env["account.account"].create(
            {
                "name": "Outstanding Receipts Test",
                "code": "TEST.OSR",
                "account_type": "asset_current",
                "company_id": cls.company_mx.id,
                "reconcile": True,
            }
        )
        cls.account_outstanding_payments = cls.env["account.account"].create(
            {
                "name": "Outstanding Payments Test",
                "code": "TEST.OSP",
                "account_type": "liability_current",
                "company_id": cls.company_mx.id,
                "reconcile": True,
            }
        )

        # ---- Partner --------------------------------------------------------
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "Test Customer MX",
                "email": "customer@test.mx",
                "company_type": "company",
                "property_account_receivable_id": cls.account_receivable.id,
                "property_account_payable_id": cls.account_payable.id,
            }
        )

        # ---- Journal --------------------------------------------------------
        cls.company_mx.write(
            {
                "account_journal_payment_debit_account_id": (
                    cls.account_outstanding_receipts.id
                ),
                "account_journal_payment_credit_account_id": (
                    cls.account_outstanding_payments.id
                ),
            }
        )
        cls.bank_journal = cls.env["account.journal"].create(
            {
                "name": "Bank Test MX",
                "type": "bank",
                "code": "BNKT",
                "company_id": cls.company_mx.id,
                "default_account_id": cls.account_bank.id,
            }
        )
        cls.sale_journal = cls.env["account.journal"].create(
            {
                "name": "Sales Test MX",
                "type": "sale",
                "code": "SLST",
                "company_id": cls.company_mx.id,
                "default_account_id": cls.account_income.id,
            }
        )

        # ---- Customer invoice (out_invoice, PPD) ----------------------------
        # PPD condition: invoice_date in current month, due date in NEXT month
        today = fields.Date.today()
        cls.invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": cls.customer.id,
                "company_id": cls.company_mx.id,
                "journal_id": cls.sale_journal.id,
                "invoice_date": today,
                "invoice_date_due": _first_day_next_month(today),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Service Test",
                            "price_unit": 5000.0,
                            "account_id": cls.account_income.id,
                        },
                    )
                ],
            }
        )
        cls.invoice.action_post()
        # Store a fake UUID on the invoice (simulating a SAT-stamped invoice)
        cls.invoice_uuid = "INVOICE-UUID-0000-0000-TEST-0001"
        cls.invoice.write({"l10n_mx_edi_cfdi_uuid": cls.invoice_uuid})

        # ---- Inbound payment (customer pays the invoice) --------------------
        cls.payment = cls.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": cls.customer.id,
                "amount": 5000.0,
                "currency_id": cls.mxn.id,
                "journal_id": cls.bank_journal.id,
                "date": today,
                "company_id": cls.company_mx.id,
            }
        )
        cls.payment.action_post()

        # ---- Reconcile payment with invoice ---------------------------------
        pay_line = cls.payment.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        inv_line = cls.invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        (pay_line | inv_line).reconcile()

        # ---- Settings -------------------------------------------------------
        cls.responsible_user = cls.env.ref("base.user_admin")
        cls.company_mx.write(
            {
                "l10n_mx_edi_cfdi_responsible_user_id": cls.responsible_user.id,
                "l10n_mx_edi_cfdi_payment_start_date": "2020-01-01",
            }
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _build_cfdi_xml(
        self,
        payment_uuid,
        payment_date,
        amount,
        invoice_uuids,
        forma_pago="03",
        saldo_insoluto="0.00",
    ):
        """Build a minimal valid CFDI 4.0 Complemento de Pago (Pagos 2.0) as bytes.

        :param payment_uuid: UUID string for the complement (TimbreFiscalDigital)
        :param payment_date: date object for FechaPago
        :param amount: float for Monto
        :param invoice_uuids: list of invoice UUID strings for DoctoRelacionado
        :param forma_pago: FormaDePagoP value (default "03" = SPEI)
        :param saldo_insoluto: ImporteSaldoInsoluto value (default "0.00")
        :return: XML bytes
        """
        NSMAP = {
            "cfdi": "http://www.sat.gob.mx/cfd/4",
            "pago20": "http://www.sat.gob.mx/Pagos20",
            "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        }
        CFDI = "http://www.sat.gob.mx/cfd/4"
        PAGO20 = "http://www.sat.gob.mx/Pagos20"
        TFD = "http://www.sat.gob.mx/TimbreFiscalDigital"

        root = etree.Element("{%s}Comprobante" % CFDI, nsmap=NSMAP)
        root.set("TipoDeComprobante", "P")
        root.set("Version", "4.0")

        complemento = etree.SubElement(root, "{%s}Complemento" % CFDI)

        pagos = etree.SubElement(complemento, "{%s}Pagos" % PAGO20)
        pagos.set("Version", "2.0")

        # Format date to ISO 8601 datetime
        if hasattr(payment_date, "strftime"):
            fecha_pago = payment_date.strftime("%Y-%m-%dT12:00:00")
        else:
            fecha_pago = str(payment_date) + "T12:00:00"

        pago = etree.SubElement(pagos, "{%s}Pago" % PAGO20)
        pago.set("FormaDePagoP", forma_pago)
        pago.set("FechaPago", fecha_pago)
        pago.set("Monto", "%.2f" % float(amount))
        pago.set("MonedaP", "MXN")

        for inv_uuid in invoice_uuids:
            docto = etree.SubElement(pago, "{%s}DoctoRelacionado" % PAGO20)
            docto.set("IdDocumento", inv_uuid)
            docto.set("ImporteSaldoInsoluto", saldo_insoluto)
            docto.set("MonedaDR", "MXN")
            docto.set("EquivalenciaDR", "1")

        totales = etree.SubElement(pagos, "{%s}Totales" % PAGO20)
        totales.set("MontoTotalPagos", "%.2f" % float(amount))

        tfd = etree.SubElement(complemento, "{%s}TimbreFiscalDigital" % TFD)
        tfd.set("UUID", payment_uuid)
        tfd.set("Version", "1.1")

        return etree.tostring(root, xml_declaration=True, encoding="UTF-8")

    def _attach_xml(self, record, xml_bytes, filename="complement.xml"):
        """Create an ir.attachment and call _process_cfdi_payment_xml directly.

        :param record: account.move recordset
        :param xml_bytes: XML content as bytes
        :param filename: attachment filename
        :return: ir.attachment record
        """
        attachment = self.env["ir.attachment"].create(
            {
                "name": filename,
                "raw": xml_bytes,
                "res_model": record._name,
                "res_id": record.id,
                "mimetype": "application/xml",
            }
        )
        record._process_cfdi_payment_xml(attachment)
        return attachment
