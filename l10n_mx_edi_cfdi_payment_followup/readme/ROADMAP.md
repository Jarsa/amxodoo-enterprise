- The state machine focuses on **requesting** complements from vendors. For
  customer collections the state is computed and surfaced, but issuing the
  complement to the customer is handled by the standard `l10n_mx_edi` flow.
- XML validation expects SPEI (`FormaDePagoP = "03"`); other payment forms are
  reported as an error and must be reviewed manually.
