import {BankRecStatementLine} from "@account_accountant/components/bank_reconciliation/statement_line/statement_line";
import {patch} from "@web/core/utils/patch";

patch(BankRecStatementLine.prototype, {
    get cfdiReceiptNeeded() {
        return (
            this.recordData.l10n_mx_edi_cfdi_is_supplier_payment &&
            this.recordData.l10n_mx_edi_cfdi_payment_state !== "not_required"
        );
    },

    get cfdiReceiptUrl() {
        return `/web/content/account.bank.statement.line/${this.record.resId}/l10n_mx_edi_cfdi_payment_receipt?download=true`;
    },

    async openCfdiReceiptWizard() {
        const action = await this.orm.call(
            "account.bank.statement.line",
            "action_open_receipt_wizard",
            [[this.record.resId]]
        );
        await this.action.doAction(action, {
            onClose: () => this.record.load(),
        });
    },
});
