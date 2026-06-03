To configure this module you need to:

1.  Go to *Accounting / Configuration / Settings*, section **CFDI Payment
    Complement Follow-up**, and set:

    - **CFDI Payment Follow-up Start Date** — only payments dated on or after
      this date are tracked. Payments before it stay *Not Required*, so
      installing the module on a database with years of history is fast.
    - **CFDI Follow-up Responsible Team** — the activity team whose members
      receive the follow-up activities (validation errors, replacements).

2.  Define the responsible team and its members. Activate the developer mode
    and go to *Settings / Technical / Email / Activity Teams*. The module ships
    a ready-to-use team named **CFDI Payment Complement Team** — open it and add
    the members, or create your own team and select it in the settings above.

3.  (Optional) On each vendor you may add a child contact tagged
    `cfdi_complement_contact`; the request email is sent to that contact when
    present, otherwise to the vendor's main email.

4.  (Optional) Tune the behaviour with these *System Parameters*
    (*Settings / Technical / Parameters / System Parameters*):

    - `l10n_mx_edi_cfdi_payment_followup_interval_days` — days to wait before a
      reminder is re-sent for a *Requested* payment (default: 5).
    - `l10n_mx_edi_cfdi_payment_date_tolerance_days` — accepted number of days
      the complement `FechaPago` may exceed the payment date (default: 2).

5.  (Optional) Activate the scheduled action **CFDI Payment Complement
    Follow-up** (*Settings / Technical / Automation / Scheduled Actions*) to
    automatically re-send reminders for overdue requests.
