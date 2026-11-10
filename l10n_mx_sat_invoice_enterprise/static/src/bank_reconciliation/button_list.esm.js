import {BankRecButtonList} from "@account_accountant/components/bank_reconciliation/button_list/button_list";
import {patch} from "@web/core/utils/patch";

patch(BankRecButtonList.prototype, {
    /**
     * Open the wizard that creates the invoices paid by the transaction from
     * the CFDIs downloaded from the SAT, then refresh the transaction.
     */
    async createInvoicesFromSatCfdis() {
        const action = await this.orm.call(
            "account.bank.statement.line",
            "action_l10n_mx_sat_create_invoices",
            [this.statementLineData.id]
        );
        await this.action.doAction(action, {
            onClose: async () => {
                await this.bankReconciliation.computeReconcileLineCountPerPartnerId(
                    this.env.model.root.records
                );
                await this.props.statementLine.load();
                this.bankReconciliation.reloadChatter();
                this.restoreFocus();
            },
        });
    },
});
