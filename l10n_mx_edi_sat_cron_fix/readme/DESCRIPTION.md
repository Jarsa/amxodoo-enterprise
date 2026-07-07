The SAT status update cron (`Automatic update of state on the SAT (for
invoices)`) of `l10n_mx_edi` includes every received CFDI attached to a posted
move in its search domain, regardless of its SAT state. Those documents never
leave the domain, so as soon as there are more than the cron batch size (100)
of them, the cron re-triggers itself after every run and processes the same
batch forever:

- The cron runs back-to-back 24/7, hammering the SAT web service.
- While a cron job runs, its `ir_cron` row stays locked, so installing or
  upgrading modules from the UI fails almost every time with *"Odoo is
  currently processing a scheduled action"*.

This module adds a *Last SAT Status Check* timestamp on the EDI documents and
excludes from the cron the received documents already checked within the last
12 hours. Each cron sweep now progresses through the whole backlog and stops,
while the daily cron still refreshes the SAT status of every received
document. The manual *Update SAT* button is not affected.
