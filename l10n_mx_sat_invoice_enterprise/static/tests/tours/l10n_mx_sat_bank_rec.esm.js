import {accountTourSteps} from "@account/js/tours/account";
import {registry} from "@web/core/registry";
import {stepUtils} from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("l10n_mx_sat_invoice_enterprise_bank_rec", {
    url: "/odoo",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        ...accountTourSteps.goToAccountMenu("Open the accounting module"),
        {
            content: "Open the bank reconciliation",
            trigger: "a.oe_kanban_action span:contains('Bank')",
            run: "click",
        },
        {
            trigger: "div.o_bank_reconciliation_kanban_renderer",
        },
        {
            content: "Open the menu of the transaction",
            trigger: "button.btn-secondary i.oi-ellipsis-v",
            run: "click",
        },
        {
            content: "Create the invoices from SAT CFDIs",
            trigger: ".dropdown-item:contains('Create from SAT CFDIs')",
            run: "click",
        },
        {
            content: "The wizard lists no CFDI yet: add them",
            trigger: ".modal div[name='document_ids'] .o_field_x2many_list_row_add a",
            run: "click",
        },
        {
            content: "Select all the CFDIs of the partner",
            trigger: ".modal:has(.o_select_button) thead .o_list_record_selector input",
            run: "click",
        },
        {
            trigger: ".modal .o_select_button:enabled",
            run: "click",
        },
        {
            content: "Both CFDIs are in the wizard",
            trigger:
                ".modal div[name='document_ids'] .o_data_row:nth-child(2):not(:has(.o_select_button))",
        },
        {
            content: "Create the invoices and match them",
            trigger: ".modal button[name='action_create_invoices']",
            run: "click",
        },
        {
            content: "The wizard is closed",
            trigger: "body:not(:has(.modal-dialog))",
        },
        {
            content: "The transaction is reloaded as matched: no menu left",
            trigger:
                "div.o_bank_reconciliation_kanban_renderer:not(:has(i.oi-ellipsis-v))",
        },
    ],
});
