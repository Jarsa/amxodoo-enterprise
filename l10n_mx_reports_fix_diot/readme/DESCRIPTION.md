This module adjusts the values of the DIOT and DPIVA text files exported from
the Mexican DIOT report so they pass the SAT validation:

- Every amount is rounded to whole pesos with the SAT rule: fractions up to
  0.50 round down and fractions above 0.50 round up.
- Each VAT amount is computed from the already rounded base
  (`rounded base x rate`), which is how the SAT validator checks it. The
  amount from accounting is kept when it does not match `base x rate`, for
  example with partially creditable VAT.
- Non-creditable VAT is reported in the column expected by the SAT DIOT
  applet instead of the one used by Odoo.
