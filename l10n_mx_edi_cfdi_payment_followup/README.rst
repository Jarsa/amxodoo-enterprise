.. image:: https://img.shields.io/badge/licence-LGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
   :alt: License: LGPL-3

=====================================
Mexico - CFDI Payment Complement Follow-up
=====================================

This module automates tracking, validation, and operational control of CFDI
Payment Complements (Complementos de Pago PPD) in Odoo.

For vendor payments it lets you request, receive, validate, and track
supplier-issued payment complements. For customer collections it detects the
payments that require a complement and surfaces the state on every linked
record.

Features
========

* New ``CFDI Payment State`` field on ``account.move`` that automatically
  reflects whether a payment complement is required, pending, requested,
  received, validated, or in error.
* Manual ``Request Complement`` button on payments and bank statement lines
  that sends a request email to the configured vendor contact.
* Automatic processing of XML attachments posted on a payment: the file is
  parsed, validated against Odoo data, and the state is transitioned.
* Internal activity created when validation fails, assigned to the configured
  CFDI follow-up responsible user.
* Scheduled action ready to be called for follow-up reminders on overdue
  requests.
* Multi-company start date setting to avoid reprocessing historical records.

Configuration
=============

Go to ``Accounting > Configuration > Settings`` and set:

* **CFDI Payment Follow-up Start Date** — only payments from this date
  onwards are tracked, so installing the module on a database with years of
  history is fast.
* **CFDI Follow-up Responsible User** — user that will receive the internal
  activity when a CFDI validation fails.

Maintainer
==========

This module is maintained by Jarsa Sistemas.

.. image:: https://www.jarsa.com.mx/web/image/website/1/logo
   :alt: Jarsa Sistemas
   :target: https://www.jarsa.com.mx
