from datetime import timedelta

from lxml import etree

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

_CFDI_NSMAP = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "pago20": "http://www.sat.gob.mx/Pagos20",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
}
# Accepted difference between the complements and the Odoo payment amount
_CFDI_AMOUNT_TOLERANCE = 1.00


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
        default="not_required",
    )
    l10n_mx_edi_cfdi_payment_last_followup_date = fields.Datetime(
        string="Last Follow-up Date",
        copy=False,
        readonly=True,
    )
    l10n_mx_edi_cfdi_payment_receipt = fields.Binary(
        string="Payment Receipt",
        attachment=True,
        copy=False,
        help="Bank transfer receipt (PDF) attached to the complement request "
        "email sent to the vendor.",
    )
    l10n_mx_edi_cfdi_payment_receipt_filename = fields.Char(
        string="Payment Receipt Filename",
        copy=False,
    )
    l10n_mx_edi_cfdi_is_supplier_payment = fields.Boolean(
        string="Is Supplier Payment",
        compute="_compute_l10n_mx_edi_cfdi_is_supplier_payment",
        store=True,
        help="Technical flag: True when the payment is reconciled against at "
        "least one vendor bill/refund. The complement request only applies to "
        "vendor payments, so the request button is hidden for customer payments.",
    )
    l10n_mx_edi_cfdi_payment_manual_ignore = fields.Boolean(
        string="Ignore CFDI Complement",
        copy=False,
        help="When enabled, this payment is treated as Not Required and the "
        "follow-up is skipped, even if it is reconciled against a PPD vendor "
        "bill. A received and valid CFDI complement XML still overrides this "
        "flag. Use the related server actions to set or revert it.",
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

    def _get_cfdi_reconciled_invoice_details(self):
        """Return reconciled invoices with the partial amount applied to each.

        Unlike :meth:`_get_cfdi_reconciled_invoices`, this accumulates the
        reconciled amount per invoice so the request email shows the value the
        payment actually applied (a partial amount when the invoice is only
        partially paid), not the invoice total.

        :return: list of dicts ``{"invoice": move, "amount": applied_amount}``
        """
        details = {}
        for line in self.line_ids:
            for partial in line.matched_debit_ids | line.matched_credit_ids:
                if partial.credit_move_id == line:
                    counterpart = partial.debit_move_id
                    amount = partial.debit_amount_currency
                else:
                    counterpart = partial.credit_move_id
                    amount = partial.credit_amount_currency
                invoice = counterpart.move_id
                if invoice == self:
                    continue
                details.setdefault(invoice, 0.0)
                details[invoice] += amount
        return [{"invoice": inv, "amount": amount} for inv, amount in details.items()]

    def _get_cfdi_payment_policy(self):
        """Return the payment policy (PUE/PPD) of an invoice for the follow-up.

        A vendor bill takes it from the ``MetodoPago`` of its own CFDI: the
        vendor's XML is the source of truth, while the computed field is only
        inferred from the dates (and stays empty on vendor bills in standard
        ``l10n_mx_edi``). Without a CFDI the computed field is used.
        """
        self.ensure_one()
        if self.is_purchase_document() and self.l10n_mx_edi_cfdi_attachment_id:
            cfdi_node = (
                self.env["l10n_mx_edi.document"]
                ._decode_cfdi_attachment(
                    self.l10n_mx_edi_cfdi_attachment_id.raw.content
                )
                .get("cfdi_node")
            )
            policy = cfdi_node.get("MetodoPago") if cfdi_node is not None else None
            if policy in ("PUE", "PPD"):
                return policy
        return self.l10n_mx_edi_payment_policy

    def _get_cfdi_payment_start_date(self):
        """Return the configured start date for the current company (or False)."""
        return self.company_id.l10n_mx_edi_cfdi_payment_start_date or False

    def _is_cfdi_payment_in_scope(self):
        """Return whether this move is a payment that needs a CFDI complement.

        Shared by the state computation and the XML processing, so a complement
        attached to an invoice or to a payment out of scope is never validated
        (nor turned into an error). The manual ignore is not part of the scope:
        a received and valid XML still overrides it.
        """
        self.ensure_one()
        # Fast-path: if the company has no follow-up start date configured,
        # the feature is disabled for this record. This avoids loading
        # related lines / reconciled invoices for the whole history when
        # the module is installed on a database with years of data.
        start_date = self._get_cfdi_payment_start_date()
        if not start_date or (self.date and self.date < start_date):
            return False

        # Rule 1: Only process payment-type entries
        if self.move_type != "entry":
            return False
        if not self.origin_payment_id and not self.statement_line_id:
            return False

        # Rule 1.1: Only journals flagged as requiring the complement.
        # Credit cards and other clearing journals are out of scope.
        if not self.journal_id.l10n_mx_edi_cfdi_payment_followup:
            return False

        # Rule 1.2: Only Mexican vendors issue a CFDI. A partner without a
        # country is kept in scope so a missing country never hides a
        # payment that does need the complement.
        country = self.partner_id.commercial_partner_id.country_id
        if country and country.code != "MX":
            return False

        # Rule 2: Must have at least one PPD reconciled invoice
        return any(
            inv._get_cfdi_payment_policy() == "PPD"
            for inv in self._get_cfdi_reconciled_invoices()
        )

    def _get_cfdi_payment_sent_documents(self):
        """Return the complement documents accepted for this payment.

        A document whose XML file was emptied (e.g. by a server action that
        clears the attachment content) is left out: Odoo can no longer read
        its UUID nor its amount, so it must not count as a complement and the
        same XML can be attached again. A document without attachment keeps
        counting as before.
        """
        return self.l10n_mx_edi_payment_document_ids.filtered(
            lambda doc: (
                doc.state == "payment_sent"
                and (not doc.attachment_id or doc.attachment_id.file_size)
            )
        )

    @api.model
    def _get_cfdi_xml_payment_amount(self, xml_raw):
        """Return the sum of ``Monto`` of a complement XML, or None if unreadable."""
        if not xml_raw:
            return None
        try:
            tree = etree.fromstring(bytes(xml_raw))
        except (etree.XMLSyntaxError, ValueError):
            return None
        pago_nodes = tree.findall(".//pago20:Pago", _CFDI_NSMAP)
        if not pago_nodes:
            return None
        return sum(float(pago.get("Monto", 0)) for pago in pago_nodes)

    def _get_cfdi_complements_amount(self, documents):
        """Return the amount of this payment covered by the given complements.

        A payment may be covered by several complements (e.g. CFE issues one
        per tax object for a single bank transfer), so their amounts are added,
        counting each UUID once. A document whose XML carries no ``Pago`` node
        (or cannot be read) is assumed to cover the whole payment, as before
        several complements were supported.
        """
        self.ensure_one()
        payment_amount = abs(self.amount_total)
        total = 0.0
        seen_uuids = set()
        for document in documents:
            uuid = (document.attachment_uuid or "").upper()
            if uuid and uuid in seen_uuids:
                continue
            seen_uuids.add(uuid)
            amount = self._get_cfdi_xml_payment_amount(document.attachment_id.raw)
            total += payment_amount if amount is None else amount
        return total

    @api.model
    def _l10n_mx_edi_cfdi_recompute_for_company(self, company, start_date):
        """Recompute the CFDI payment state for moves in scope of the company.

        Targets only payment-type entries from ``start_date`` onwards so the
        recomputation cost is bounded to the configured range, never the whole
        history.
        """
        moves = self.search(
            [
                ("company_id", "=", company.id),
                ("move_type", "=", "entry"),
                ("date", ">=", start_date),
            ]
        )
        if moves:
            self.env.add_to_compute(
                self._fields["l10n_mx_edi_cfdi_payment_state"], moves
            )
            self.env.add_to_compute(
                self._fields["l10n_mx_edi_cfdi_is_supplier_payment"], moves
            )

    @api.depends(
        "payment_state",
        "move_type",
        "l10n_mx_edi_payment_policy",
        "line_ids.matched_debit_ids",
        "line_ids.matched_credit_ids",
        # CFDI attached to a reconciled invoice after the reconciliation
        "line_ids.matched_debit_ids.debit_move_id.move_id"
        ".l10n_mx_edi_cfdi_attachment_id",
        "line_ids.matched_credit_ids.credit_move_id.move_id"
        ".l10n_mx_edi_cfdi_attachment_id",
        "l10n_mx_edi_payment_document_ids.state",
        "l10n_mx_edi_payment_document_ids.attachment_id",
        # Complement XML emptied after it was accepted
        "l10n_mx_edi_payment_document_ids.attachment_id.file_size",
        "amount_total",
        "l10n_mx_edi_cfdi_payment_manual_ignore",
        "attachment_ids",
        "journal_id.l10n_mx_edi_cfdi_payment_followup",
        "partner_id.country_id",
    )
    def _compute_l10n_mx_edi_cfdi_payment_state(self):
        for record in self:
            if not record._is_cfdi_payment_in_scope():
                record.l10n_mx_edi_cfdi_payment_state = "not_required"
                continue

            # Received complement documents always win, even over a manual
            # ignore (a received and valid XML must never be discarded) or a
            # stored error/requested state (a payment that already has its
            # complement must not be requested again). Validated once they
            # cover the payment, Received while some complement is missing.
            sent_documents = record._get_cfdi_payment_sent_documents()
            if sent_documents:
                covered = record._get_cfdi_complements_amount(sent_documents)
                if covered >= abs(record.amount_total) - _CFDI_AMOUNT_TOLERANCE:
                    record.l10n_mx_edi_cfdi_payment_state = "validated"
                else:
                    record.l10n_mx_edi_cfdi_payment_state = "received"
                continue

            # Manual ignore: user explicitly marked this payment as not
            # requiring a complement. Respect it (reversible via server action).
            if record.l10n_mx_edi_cfdi_payment_manual_ignore:
                record.l10n_mx_edi_cfdi_payment_state = "not_required"
                continue

            # Read the stored state from DB to avoid reading the field being
            # computed (which would cause circular evaluation issues).
            self.env.cr.execute(
                "SELECT l10n_mx_edi_cfdi_payment_state FROM account_move WHERE id = %s",
                [record.id],
            )
            row = self.env.cr.fetchone()
            stored_state = row[0] if row else False

            # Preserve manually-set states only when eligibility still holds
            if stored_state in ("error", "requested"):
                record.l10n_mx_edi_cfdi_payment_state = stored_state
                continue

            # Default: pending
            record.l10n_mx_edi_cfdi_payment_state = "pending"

    @api.depends(
        "line_ids.matched_debit_ids",
        "line_ids.matched_credit_ids",
    )
    def _compute_l10n_mx_edi_cfdi_is_supplier_payment(self):
        for record in self:
            reconciled_invoices = record._get_cfdi_reconciled_invoices()
            record.l10n_mx_edi_cfdi_is_supplier_payment = any(
                inv.move_type in ("in_invoice", "in_refund")
                for inv in reconciled_invoices
            )

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
            new_state = record.l10n_mx_edi_cfdi_payment_state
            if (
                prev_uuid
                and prev_state == "validated"
                and new_state in ("pending", "not_required")
            ):
                record.with_context(cfdi_followup_skip_notify=True).message_post(
                    body=self.env._(
                        "Warning: This payment was un-reconciled from a PPD invoice "
                        "but a validated CFDI payment complement already existed "
                        "(UUID: %s). Please review the fiscal situation.",
                        prev_uuid,
                    ),
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
            # Re-reconciliation: when the state transitions into 'pending'
            # (typically after a reconciliation is applied), reprocess any
            # XML attachment already present so the state recovers to
            # 'validated' (or 'error') without manual intervention.
            if new_state == "pending" and prev_state != "pending":
                xml_attachments = record.attachment_ids.filtered(
                    lambda a: (
                        (a.name or "").lower().endswith(".xml")
                        or "xml" in (a.mimetype or "").lower()
                    )
                )
                for attachment in xml_attachments:
                    record._process_cfdi_payment_xml(attachment)
        return res

    # -------------------------------------------------------------------------
    # Public actions
    # -------------------------------------------------------------------------

    def action_request_cfdi_complement(self):
        """Send a complement request email to the vendor contact.

        Active only when state is 'pending', 'error', 'received' (a complement
        is still missing) or 'requested' (cron resend).
        """
        for record in self:
            if record.l10n_mx_edi_cfdi_payment_state not in (
                "pending",
                "error",
                "received",
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
                    self.env._(
                        "No email address found for partner %s. "
                        "Please configure a contact with the 'cfdi_complement_contact' "
                        "tag or a main email.",
                        record.partner_id.display_name,
                    )
                )

            # Send mail template
            template = self.env.ref(
                "l10n_mx_edi_cfdi_payment_followup"
                ".mail_template_cfdi_complement_request",
                raise_if_not_found=False,
            )
            if template:
                email_values = {"email_to": recipient_email}
                # Attach only the bank transfer receipt (uploaded in the
                # dedicated field), not arbitrary chatter attachments.
                if record.l10n_mx_edi_cfdi_payment_receipt:
                    receipt_attachment = self.env["ir.attachment"].create(
                        {
                            "name": (
                                record.l10n_mx_edi_cfdi_payment_receipt_filename
                                or self.env._("Payment Receipt.pdf")
                            ),
                            "raw": record.l10n_mx_edi_cfdi_payment_receipt,
                            "mimetype": "application/pdf",
                        }
                    )
                    email_values["attachment_ids"] = [
                        Command.set(receipt_attachment.ids)
                    ]
                template.send_mail(
                    record.id,
                    force_send=False,
                    email_values=email_values,
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
                body=self.env._(
                    "Complement request email sent to %s.", recipient_email
                ),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

    def action_cfdi_ignore(self):
        """Mark the payment as Not Required (ignore the complement follow-up).

        Reversible via :meth:`action_cfdi_unignore`. A validated complement
        document still overrides this flag in the state computation.
        """
        for record in self:
            if record.l10n_mx_edi_cfdi_payment_manual_ignore:
                continue
            record.l10n_mx_edi_cfdi_payment_manual_ignore = True
            record.message_post(
                body=self.env._(
                    "CFDI payment complement marked as Not Required (ignored)."
                ),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

    def action_cfdi_unignore(self):
        """Revert the manual ignore so the follow-up state is recomputed."""
        for record in self:
            if not record.l10n_mx_edi_cfdi_payment_manual_ignore:
                continue
            record.l10n_mx_edi_cfdi_payment_manual_ignore = False
            record.message_post(
                body=self.env._(
                    "CFDI payment complement follow-up re-enabled (ignore reverted)."
                ),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

    def action_cfdi_payment_followup(self):
        """Re-send complement requests for overdue 'requested' payments.

        Intended to be called by a scheduled action (cron).
        """
        interval_days = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_int("l10n_mx_edi_cfdi_payment_followup_interval_days", default=5)
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

    def _get_cfdi_responsible_team(self):
        """Return the configured responsible team for CFDI follow-up."""
        team = self.company_id.l10n_mx_edi_cfdi_responsible_team_id
        if not team:
            raise UserError(
                self.env._(
                    "CFDI responsible team is not configured for company %s. "
                    "Please go to Accounting > Settings and set the "
                    "CFDI Follow-up Responsible Team.",
                    self.company_id.name,
                )
            )
        return team

    @api.model
    def _get_cfdi_error_activity_summary(self):
        """Return the canonical summary used for CFDI error activities.

        Centralized to keep create/close paths in sync regardless of locale.
        """
        return self.env._("CFDI Complement Error")

    def _create_cfdi_payment_activity(self, error_message):
        """Create a follow-up activity for the configured responsible team.

        Uses this module's dedicated activity type; the ``mail_activity_team``
        mixin assigns the team (and its members) automatically.
        """
        team = self._get_cfdi_responsible_team()
        self.with_context(force_activity_team=team).activity_schedule(
            "l10n_mx_edi_cfdi_payment_followup.mail_activity_type_cfdi_complement",
            summary=self._get_cfdi_error_activity_summary(),
            note=error_message,
        )

    def _close_cfdi_payment_error_activities(self):
        """Mark open CFDI error activities on this record as done."""
        summary = self._get_cfdi_error_activity_summary()
        activities = self.activity_ids.filtered(lambda a: a.summary == summary)
        if activities:
            activities.action_feedback(
                feedback=self.env._("CFDI payment complement validated successfully.")
            )

    def _process_cfdi_payment_xml(self, attachment):
        """Parse and validate a CFDI payment complement XML attachment.

        A payment may be covered by several complements: each XML is validated
        on its own and its amount is added to the complements already accepted
        for the payment, which becomes Validated once they cover it and
        Received while some complement is still missing.

        Called from _message_post_after_hook when an XML attachment is posted.
        """
        # Step 1: filter by extension / mimetype
        filename = (attachment.name or "").lower()
        mimetype = (attachment.mimetype or "").lower()
        if not filename.endswith(".xml") and "xml" not in mimetype:
            return

        # Step 2: parse XML
        try:
            tree = etree.fromstring(attachment.raw.content)
        except etree.XMLSyntaxError:
            return

        # Step 3: validate TipoDeComprobante == "P"
        tipo = tree.get("TipoDeComprobante")
        if tipo != "P":
            return

        # Only payments that need a complement are validated: an XML attached
        # to an invoice or to a payment out of scope is kept as a plain file.
        if not self._is_cfdi_payment_in_scope():
            return

        # Step 4: extract UUID
        tfd_node = tree.find(".//tfd:TimbreFiscalDigital", _CFDI_NSMAP)
        uuid = tfd_node.get("UUID") if tfd_node is not None else None
        if not uuid:
            self._on_cfdi_xml_error(self.env._("UUID not found in XML"))
            return

        # Idempotency: this complement was already accepted for the payment.
        # Its document drives the state, which is recovered by the compute if
        # it was lost (e.g., un-reconcile + re-reconcile cycle).
        sent_documents = self._get_cfdi_payment_sent_documents()
        accepted_uuids = {(doc.attachment_uuid or "").upper() for doc in sent_documents}
        if uuid.upper() in accepted_uuids:
            return

        # Step 5: extract Pago nodes
        pago_nodes = tree.findall(".//pago20:Pago", _CFDI_NSMAP)
        if not pago_nodes:
            self._on_cfdi_xml_error(self.env._("No Pago node found"))
            return

        # Step 6: run all validation rules, accumulate errors
        errors = self._validate_cfdi_payment_xml(pago_nodes)

        if errors:
            combined = "\n".join(f"- {e}" for e in errors)
            self._on_cfdi_xml_error(combined)
            return

        # Step 7: sum of Monto plus the complements already accepted must not
        # exceed the Odoo payment amount (tolerance ±1.00). When it does, this
        # XML is a replacement if it covers the payment by itself.
        payment_amount = abs(self.amount_total)
        xml_amount = sum(float(pago.get("Monto", 0)) for pago in pago_nodes)
        covered = self._get_cfdi_complements_amount(sent_documents) + xml_amount
        replaced_documents = self.env["l10n_mx_edi.document"]
        if covered > payment_amount + _CFDI_AMOUNT_TOLERANCE:
            if abs(xml_amount - payment_amount) > _CFDI_AMOUNT_TOLERANCE:
                if sent_documents:
                    error = self.env._(
                        "Amount mismatch: complements total %(total)s vs Odoo %(odoo)s",
                        total=covered,
                        odoo=payment_amount,
                    )
                else:
                    error = self.env._(
                        "Amount mismatch: XML total %(xml)s vs Odoo %(odoo)s",
                        xml=xml_amount,
                        odoo=payment_amount,
                    )
                self._on_cfdi_xml_error(f"- {error}")
                return
            replaced_documents = sent_documents
            covered = xml_amount
        is_complete = covered >= payment_amount - _CFDI_AMOUNT_TOLERANCE

        # Step 8: success — create l10n_mx_edi.document so UUID is auto-computed
        reconciled_invoices = self._get_cfdi_reconciled_invoices()
        document_values = {
            "move_id": self.id,
            "company_id": self.company_id.id,
            "invoice_ids": [Command.set(reconciled_invoices.ids)],
            "state": "payment_sent",
            "sat_state": "not_defined",
            "message": None,
            "attachment_id": attachment.id,
        }
        self.env["l10n_mx_edi.document"]._create_update_payment_document(
            self, document_values
        )
        # Explicitly set state (guard would block auto-compute for 'requested'
        # state). Also clear any manual ignore: a received and valid CFDI
        # complement must never be discarded just because the payment was
        # marked Not Required (ignored) beforehand.
        self.with_context(cfdi_followup_skip_notify=True).write(
            {
                "l10n_mx_edi_cfdi_payment_state": (
                    "validated" if is_complete else "received"
                ),
                "l10n_mx_edi_cfdi_payment_manual_ignore": False,
            }
        )

        if not is_complete:
            # Amounts with the 2 decimals of the CFDI, not the currency's: some
            # databases raise the currency precision (e.g. to 6 decimals).
            currency = self.currency_id.name
            missing = payment_amount - covered
            self.message_post(
                body=self.env._(
                    "Partial CFDI payment complement received. UUID: %(uuid)s. "
                    "The complements received cover %(covered)s of %(total)s; "
                    "%(missing)s is still missing.",
                    uuid=uuid,
                    covered=f"{formatLang(self.env, covered)} {currency}",
                    total=f"{formatLang(self.env, payment_amount)} {currency}",
                    missing=f"{formatLang(self.env, missing)} {currency}",
                ),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
            return

        # Close any prior error activities now that validation succeeded
        self._close_cfdi_payment_error_activities()

        if replaced_documents:
            previous_uuid = ", ".join(
                filter(None, replaced_documents.mapped("attachment_uuid"))
            )
            self.message_post(
                body=self.env._(
                    "Replacement CFDI payment complement received. "
                    "Previous UUID: %(prev)s — New UUID: %(new)s. "
                    "Please verify the fiscal status of both documents.",
                    prev=previous_uuid,
                    new=uuid,
                ),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
            self._create_cfdi_payment_activity(
                self.env._(
                    "A replacement complement was received for this payment.\n"
                    "Previous UUID: %(prev)s\nNew UUID: %(new)s",
                    prev=previous_uuid,
                    new=uuid,
                )
            )
        else:
            self.message_post(
                body=self.env._(
                    "CFDI payment complement validated successfully. UUID: %(uuid)s",
                    uuid=uuid,
                ),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

    def _on_cfdi_xml_error(self, combined_error):
        """Set state to error, create activity and post chatter on failure."""
        self.with_context(cfdi_followup_skip_notify=True).write(
            {"l10n_mx_edi_cfdi_payment_state": "error"}
        )
        self._create_cfdi_payment_activity(combined_error)
        self.message_post(
            body=self.env._(
                "CFDI payment complement validation failed:\n%s", combined_error
            ),
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

    def _validate_cfdi_payment_xml(self, pago_nodes):
        """Run the validation rules of one complement and return the errors.

        The amount is checked in :meth:`_process_cfdi_payment_xml`
        against all the complements of the payment, not one XML alone.
        """
        from datetime import datetime

        errors = []

        # Rule 4: FormaDePagoP must be "03" (SPEI)
        for pago in pago_nodes:
            forma = pago.get("FormaDePagoP", "")
            if forma != "03":
                errors.append(
                    self.env._("Payment form is not SPEI (03), found: %s", forma)
                )

        # Rule 5: FechaPago must be >= record.date (within forward tolerance)
        tolerance_days = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_int("l10n_mx_edi_cfdi_payment_date_tolerance_days", default=2)
        )
        for pago in pago_nodes:
            fecha_str = pago.get("FechaPago", "")
            if fecha_str:
                try:
                    fecha = datetime.fromisoformat(fecha_str).date()
                except ValueError:
                    errors.append(
                        self.env._(
                            "Invalid FechaPago format: %(fecha)s", fecha=fecha_str
                        )
                    )
                    continue
                record_date = self.date
                if record_date:
                    if fecha < record_date:
                        errors.append(
                            self.env._(
                                "Complement date %(fecha)s precedes"
                                " payment date %(date)s",
                                fecha=fecha,
                                date=record_date,
                            )
                        )
                    elif fecha > record_date + timedelta(days=tolerance_days):
                        errors.append(
                            self.env._(
                                "Complement date %(fecha)s exceeds"
                                " payment date %(date)s"
                                " by more than %(days)d day(s)",
                                fecha=fecha,
                                date=record_date,
                                days=tolerance_days,
                            )
                        )

        # Collect reconciled invoice UUIDs. UUIDs are compared in uppercase: the
        # SAT does not distinguish case, and some PACs stamp the invoice in
        # lowercase while the complement references it in uppercase.
        reconciled_invoices = self._get_cfdi_reconciled_invoices()
        reconciled_uuids = {
            inv.l10n_mx_edi_cfdi_uuid.upper()
            for inv in reconciled_invoices
            if inv.l10n_mx_edi_cfdi_uuid
        }

        for pago in pago_nodes:
            for docto in pago.findall("pago20:DoctoRelacionado", _CFDI_NSMAP):
                inv_uuid = docto.get("IdDocumento", "")

                # Rule 6: IdDocumento must match a reconciled invoice UUID
                if inv_uuid.upper() not in reconciled_uuids:
                    errors.append(
                        self.env._(
                            "Invoice UUID %(uuid)s not found in reconciled invoices",
                            uuid=inv_uuid,
                        )
                    )

        # The outstanding balance (ImpSaldoInsoluto) is not validated: a PPD
        # invoice may be paid in installments, so a complement leaving a
        # balance is valid.

        return errors

    # -------------------------------------------------------------------------
    # Mail hook
    # -------------------------------------------------------------------------

    def _message_post_after_hook(self, message):
        res = super()._message_post_after_hook(message)
        for attachment in message.attachment_ids:
            self._process_cfdi_payment_xml(attachment)
        return res
