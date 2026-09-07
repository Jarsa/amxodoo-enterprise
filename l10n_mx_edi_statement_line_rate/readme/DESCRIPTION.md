When a bank statement line in a foreign currency (for example USD) is
reconciled against customer invoices issued in the company currency (MXN), the
bank reconciliation widget keeps the receivable counterpart in MXN inside a USD
journal entry and leaves the exchange difference to be booked as a write-off.
The standard CFDI payment complement then reads the reconciled MXN amount as if
it were USD and stamps `MonedaP="USD"`, `TipoCambioP="1"`, `Monto` equal to the
MXN amount and the tax totals of the whole invoice.

This module takes the amount and the exchange rate from the bank liquidity line
instead, so the complement reports the USD actually received, the real
`TipoCambioP`, the `EquivalenciaDR` implied by the reconciled amount and tax
totals (`TotalTrasladosImpuestoIVA16`, `MontoTotalPagos`) expressed at the real
rate, as required by the SAT filling guide for Pagos 2.0.
