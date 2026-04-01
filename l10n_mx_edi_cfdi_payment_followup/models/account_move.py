from datetime import timedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

_CFDI_NSMAP = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "pago20": "http://www.sat.gob.mx/Pagos20",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
}


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_mx_edi_cfdi_payment_state = fields.Selection(
        selection=[
            ("not_required", "Not Required"),
            ("pending", "Pending"),
            ("requested", "Requested"),
            ("received", "Received"),
            ("validated", "Validated"),
            ("error", "Error"),
        ],
        string="CFDI Payment State",
        compute="_compute_l10n_mx_edi_cfdi_payment_state",
        store=True,
        readonly=False,
        copy=False,
        tracking=True,
    )
    l10n_mx_edi_cfdi_payment_last_followup_date = fields.Datetime(
        string="Last Follow-up Date",
        copy=False,
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------

    def _get_cfdi_reconciled_invoices(self):
        """Return invoices reconciled against this payment move."""
        invoices = self.env["account.move"]
        for line in self.line_ids:
            for partial in line.matched_debit_ids | line.matched_credit_ids:
                counterpart = (
                    partial.debit_move_id
                    if partial.credit_move_id == line
                    else partial.credit_move_id
                )
                if counterpart.move_id != self:
                    invoices |= counterpart.move_id
        return invoices

    def _get_cfdi_payment_start_date(self):
        """Return the configured start date for the current company (or False)."""
        return self.company_id.l10n_mx_edi_cfdi_payment_start_date or False

    @api.depends(
        "payment_state",
        "move_type",
        "l10n_mx_edi_payment_policy",
        "line_ids.matched_debit_ids",
        "line_ids.matched_credit_ids",
        "l10n_mx_edi_payment_document_ids.state",
        "attachment_ids",
    )
    def _compute_l10n_mx_edi_cfdi_payment_state(self):
        for record in self:
            # Read the stored state from DB to avoid reading the field being
            # computed (which would cause circular evaluation issues).
            self.env.cr.execute(
                "SELECT l10n_mx_edi_cfdi_payment_state "
                "FROM account_move WHERE id = %s",
                [record.id],
            )
            row = self.env.cr.fetchone()
            stored_state = row[0] if row else False

            # Preserve manually-set states that should not be overwritten
            if stored_state in ("error", "requested"):
                continue

            # Rule 1: Only process payment-type entries
            if record.move_type != "entry":
                record.l10n_mx_edi_cfdi_payment_state = "not_required"
                continue
            if not record.payment_id and not record.statement_line_id:
                record.l10n_mx_edi_cfdi_payment_state = "not_required"
                continue

            # Rule 2: Check start date
            start_date = record._get_cfdi_payment_start_date()
            if start_date and record.date and record.date < start_date:
                record.l10n_mx_edi_cfdi_payment_state = "not_required"
                continue

            # Rule 3: Must have at least one PPD reconciled invoice
            reconciled_invoices = record._get_cfdi_reconciled_invoices()
            has_ppd = any(
                inv.l10n_mx_edi_payment_policy == "PPD" for inv in reconciled_invoices
            )
            if not has_ppd:
                record.l10n_mx_edi_cfdi_payment_state = "not_required"
                continue

            # Rule 4: A validated complement document exists
            has_sent_document = any(
                doc.state == "payment_sent"
                for doc in record.l10n_mx_edi_payment_document_ids
            )
            if has_sent_document:
                record.l10n_mx_edi_cfdi_payment_state = "validated"
                continue

            # Default: pending
            record.l10n_mx_edi_cfdi_payment_state = "pending"

    # -------------------------------------------------------------------------
    # Write override — detect un-reconcile with existing UUID
    # -------------------------------------------------------------------------

    def write(self, vals):
        # Capture UUID before write to detect reconciliation breaks
        uuid_before = {r.id: r.l10n_mx_edi_cfdi_uuid for r in self}
        state_before = {r.id: r.l10n_mx_edi_cfdi_payment_state for r in self}
        res = super().write(vals)
        # After write: if state changed away from 'validated' and UUID was set,
        # notify in chatter (skip if context flag is set to avoid recursion)
        if self.env.context.get("cfdi_followup_skip_notify"):
            return res
        for record in self:
            prev_uuid = uuid_before.get(record.id)
            prev_state = state_before.get(record.id)
            if (
                prev_uuid
                and prev_state == "validated"
                and record.l10n_mx_edi_cfdi_payment_state in ("pending", "not_required")
            ):
                record.with_context(cfdi_followup_skip_notify=True).message_post(
                    body=_(
                        "Warning: This payment was un-reconciled from a PPD invoice "
                        "but a validated CFDI payment complement already existed "
                        "(UUID: %s). Please review the fiscal situation."
                    )
                    % prev_uuid,
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
        return res

    # -------------------------------------------------------------------------
    # Public actions
    # -------------------------------------------------------------------------

    def action_request_cfdi_complement(self):
        """Send a complement request email to the vendor contact.

        Active only when state is 'pending', 'error', or 'requested' (cron resend).
        """
        for record in self:
            if record.l10n_mx_edi_cfdi_payment_state not in (
                "pending",
                "error",
                "requested",
            ):
                continue
            # Find recipient: partner with tag 'cfdi_complement_contact' or main email
            recipient_email = False
            if record.partner_id:
                tagged_partner = record.partner_id.child_ids.filtered(
                    lambda p: any(
                        t.name == "cfdi_complement_contact" for t in p.category_id
                    )
                )
                if tagged_partner:
                    recipient_email = tagged_partner[0].email
                if not recipient_email:
                    recipient_email = record.partner_id.email

            if not recipient_email:
                raise UserError(
                    _(
                        "No email address found for partner %s. "
                        "Please configure a contact with the 'cfdi_complement_contact' "
                        "tag or a main email."
                    )
                    % record.partner_id.display_name
                )

            # Send mail template
            template = self.env.ref(
                "l10n_mx_edi_cfdi_payment_followup"
                ".mail_template_cfdi_complement_request",
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(
                    record.id,
                    force_send=False,
                    email_values={"email_to": recipient_email},
                )

            # Update state
            record.with_context(cfdi_followup_skip_notify=True).write(
                {
                    "l10n_mx_edi_cfdi_payment_state": "requested",
                    "l10n_mx_edi_cfdi_payment_last_followup_date": (
                        fields.Datetime.now()
                    ),
                }
            )
            record.message_post(
                body=_("Complement request email sent to %s.") % recipient_email,
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

    def action_cfdi_payment_followup(self):
        """Re-send complement requests for overdue 'requested' payments.

        Intended to be called by a scheduled action (cron).
        """
        interval_days = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("l10n_mx_edi_cfdi_payment_followup_interval_days", default=5)
        )
        cutoff = fields.Datetime.now() - timedelta(days=interval_days)

        records = self.search([("l10n_mx_edi_cfdi_payment_state", "=", "requested")])
        for record in records:
            start_date = record.company_id.l10n_mx_edi_cfdi_payment_start_date
            if start_date and record.date and record.date < start_date:
                continue
            if (
                record.l10n_mx_edi_cfdi_payment_last_followup_date
                and record.l10n_mx_edi_cfdi_payment_last_followup_date > cutoff
            ):
                continue
            record.action_request_cfdi_complement()

    # -------------------------------------------------------------------------
    # XML processing
    # -------------------------------------------------------------------------

    def _get_cfdi_responsible_user(self):
        """Return the configured responsible user for CFDI follow-up."""
        user = self.company_id.l10n_mx_edi_cfdi_responsible_user_id
        if not user:
            raise UserError(
                _(
                    "CFDI responsible user is not configured for company %s. "
                    "Please go to Accounting > Settings and set the "
                    "CFDI Follow-up Responsible User."
                )
                % self.company_id.name
            )
        return user

    def _create_cfdi_payment_activity(self, error_message):
        """Create a To-Do activity assigned to the responsible user."""
        responsible_user = self._get_cfdi_responsible_user()
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            summary=_("CFDI Complement Error"),
            note=error_message,
            user_id=responsible_user.id,
        )

    def _process_cfdi_payment_xml(self, attachment):
        """Parse and validate a CFDI payment complement XML attachment.

        Called from _message_post_after_hook when an XML attachment is posted.
        """
        from lxml import etree  # noqa: PLC0415

        # Step 1: filter by extension / mimetype
        filename = (attachment.name or "").lower()
        mimetype = (attachment.mimetype or "").lower()
        if not filename.endswith(".xml") and "xml" not in mimetype:
            return

        # Step 2: parse XML
        try:
            tree = etree.fromstring(attachment.raw)
        except etree.XMLSyntaxError:
            return

        # Step 3: validate TipoDeComprobante == "P"
        tipo = tree.get("TipoDeComprobante")
        if tipo != "P":
            return

        # Step 4: extract UUID
        tfd_node = tree.find(".//tfd:TimbreFiscalDigital", _CFDI_NSMAP)
        uuid = tfd_node.get("UUID") if tfd_node is not None else None
        if not uuid:
            self._on_cfdi_xml_error(_("UUID not found in XML"))
            return

        # Idempotency: same UUID already validated in an existing document
        if self.l10n_mx_edi_cfdi_uuid and self.l10n_mx_edi_cfdi_uuid == uuid:
            return

        # Replacement: different UUID while one already stored
        is_replacement = bool(
            self.l10n_mx_edi_cfdi_uuid and self.l10n_mx_edi_cfdi_uuid != uuid
        )
        previous_uuid = self.l10n_mx_edi_cfdi_uuid if is_replacement else None

        # Step 5: extract Pago nodes
        pago_nodes = tree.findall(".//pago20:Pago", _CFDI_NSMAP)
        if not pago_nodes:
            self._on_cfdi_xml_error(_("No Pago node found"))
            return

        # Step 6: run all validation rules, accumulate errors
        errors = self._validate_cfdi_payment_xml(pago_nodes)

        if errors:
            combined = "\n".join("- %s" % e for e in errors)
            self._on_cfdi_xml_error(combined)
            return

        # Step 7: success — create l10n_mx_edi.document so UUID is auto-computed
        reconciled_invoices = self._get_cfdi_reconciled_invoices()
        document_values = {
            "move_id": self.id,
            "invoice_ids": [Command.set(reconciled_invoices.ids)],
            "state": "payment_sent",
            "sat_state": "not_defined",
            "message": None,
            "attachment_id": attachment.id,
        }
        self.env["l10n_mx_edi.document"]._create_update_payment_document(
            self, document_values
        )
        # Explicitly set state (guard would block auto-compute for 'requested' state)
        self.with_context(cfdi_followup_skip_notify=True).write(
            {"l10n_mx_edi_cfdi_payment_state": "validated"}
        )

        if is_replacement:
            self.message_post(
                body=_(
                    "Replacement CFDI payment complement received. "
                    "Previous UUID: %s — New UUID: %s. "
                    "Please verify the fiscal status of both documents."
                )
                % (previous_uuid, uuid),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
            self._create_cfdi_payment_activity(
                _(
                    "A replacement complement was received for this payment.\n"
                    "Previous UUID: %s\nNew UUID: %s"
                )
                % (previous_uuid, uuid)
            )
        else:
            self.message_post(
                body=_("CFDI payment complement validated successfully. UUID: %s")
                % uuid,
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

    def _on_cfdi_xml_error(self, combined_error):
        """Set state to error, create activity and post chatter on validation failure."""
        self.with_context(cfdi_followup_skip_notify=True).write(
            {"l10n_mx_edi_cfdi_payment_state": "error"}
        )
        self._create_cfdi_payment_activity(combined_error)
        self.message_post(
            body=_("CFDI payment complement validation failed:\n%s") % combined_error,
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

    def _validate_cfdi_payment_xml(self, pago_nodes):
        """Run all 8 validation rules and return a list of error messages."""
        from datetime import datetime  # noqa: PLC0415

        errors = []

        # Rule 4: FormaDePagoP must be "03" (SPEI)
        for pago in pago_nodes:
            forma = pago.get("FormaDePagoP", "")
            if forma != "03":
                errors.append(_("Payment form is not SPEI (03), found: %s") % forma)

        # Rule 5: FechaPago must be >= record.date (within forward tolerance)
        tolerance_days = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("l10n_mx_edi_cfdi_payment_date_tolerance_days", default=2)
        )
        for pago in pago_nodes:
            fecha_str = pago.get("FechaPago", "")
            if fecha_str:
                try:
                    fecha = datetime.fromisoformat(fecha_str).date()
                except ValueError:
                    errors.append(_("Invalid FechaPago format: %s") % fecha_str)
                    continue
                record_date = self.date
                if record_date:
                    if fecha < record_date:
                        errors.append(
                            _("Complement date %s precedes payment date %s")
                            % (fecha, record_date)
                        )
                    elif fecha > record_date + timedelta(days=tolerance_days):
                        errors.append(
                            _(
                                "Complement date %s exceeds payment date %s "
                                "by more than %d day(s)"
                            )
                            % (fecha, record_date, tolerance_days)
                        )

        # Collect reconciled invoice UUIDs
        reconciled_invoices = self._get_cfdi_reconciled_invoices()
        reconciled_uuids = {
            inv.l10n_mx_edi_cfdi_uuid
            for inv in reconciled_invoices
            if inv.l10n_mx_edi_cfdi_uuid
        }

        for pago in pago_nodes:
            for docto in pago.findall("pago20:DoctoRelacionado", _CFDI_NSMAP):
                inv_uuid = docto.get("IdDocumento", "")

                # Rule 6: IdDocumento must match a reconciled invoice UUID
                if inv_uuid not in reconciled_uuids:
                    errors.append(
                        _("Invoice UUID %s not found in reconciled invoices") % inv_uuid
                    )

                # Rule 7: ImporteSaldoInsoluto must be "0.00"
                saldo = docto.get("ImporteSaldoInsoluto", "")
                if saldo and saldo != "0.00":
                    errors.append(
                        _("Outstanding balance not zero for invoice %s: %s")
                        % (inv_uuid, saldo)
                    )

        # Rule 8: Sum of Monto must match Odoo payment amount (tolerance ±1.00)
        xml_total = sum(float(pago.get("Monto", 0)) for pago in pago_nodes)
        odoo_amount = abs(self.amount_total)
        if abs(xml_total - odoo_amount) > 1.00:
            errors.append(
                _("Amount mismatch: XML total %(xml)s vs Odoo %(odoo)s")
                % {"xml": xml_total, "odoo": odoo_amount}
            )

        return errors

    # -------------------------------------------------------------------------
    # Mail hook
    # -------------------------------------------------------------------------

    def _message_post_after_hook(self, new_message, message_values):
        # EXTENDS account AccountMove
        res = super()._message_post_after_hook(new_message, message_values)
        for attachment in new_message.attachment_ids:
            self._process_cfdi_payment_xml(attachment)
        return res
