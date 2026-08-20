To configure this module you need to:

1.  Go to *Accounting / Configuration / Settings*, section **CFDI Payment
    Complement Follow-up**, and set:

    - **CFDI Payment Follow-up Start Date** — only payments dated on or after
      this date are tracked. Payments before it stay *Not Required*, so
      installing the module on a database with years of history is fast.
    - **CFDI Follow-up Responsible Team** — the activity team whose members
      receive the follow-up activities (validation errors, replacements).
    - **CFDI Payment Request CC Users** — (optional) select internal users whose
      emails will be included in the request email body to ask the vendor to CC them.

2.  Go to *Accounting / Configuration / Journals* and tick **Requires CFDI
    Payment Complement** on every bank or cash journal whose payments do need a
    complement. Payments registered in any other journal (credit cards,
    clearing journals, and so on) stay *Not Required*. Foreign vendors are
    excluded automatically: a partner whose country is not Mexico never issues
    a CFDI, so its payments are never tracked.

3.  Define the responsible team and its members. Activate the developer mode
    and go to *Settings / Technical / Email / Activity Teams*. The module ships
    a ready-to-use team named **CFDI Payment Complement Team** — open it and add
    the members, or create your own team and select it in the settings above.

4.  (Optional) On each vendor you may add a child contact tagged
    `cfdi_complement_contact`; the request email is sent to that contact when
    present, otherwise to the vendor's main email.

5.  (Optional) Tune the behaviour with these *System Parameters*
    (*Settings / Technical / Parameters / System Parameters*):

    - `l10n_mx_edi_cfdi_payment_followup_interval_days` — days to wait before a
      reminder is re-sent for a *Requested* payment (default: 5).
    - `l10n_mx_edi_cfdi_payment_date_tolerance_days` — accepted number of days
      the complement `FechaPago` may exceed the payment date (default: 2).

6.  (Optional) Activate the scheduled action **CFDI Payment Complement
    Follow-up** (*Settings / Technical / Automation / Scheduled Actions*) to
    automatically re-send reminders for overdue requests.
