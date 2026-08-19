/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { session } from "@web/session";
import { registry } from "@web/core/registry";

try {
    // 1. Patch ListController to hide Export in Action Menu when restricted
    patch(ListController.prototype, {
        get isExportEnable() {
            const resModel = this.props && this.props.resModel;
            const hideGlobal = Boolean(session.hide_export_globally);
            const hideModel = Boolean(
                resModel &&
                session.export_restricted_models &&
                session.export_restricted_models.includes(resModel)
            );
            if (hideGlobal || hideModel) {
                return false;
            }
            return Boolean(this._isExportEnable);
        },
        set isExportEnable(value) {
            this._isExportEnable = value;
        },
    });
} catch (e) {
    console.error("Access Management: Failed to patch ListController", e);
}

try {
    // 2. Patch Cog Menu for Import Records safely
    const cogMenuRegistry = registry.category("cogMenu");
    if (cogMenuRegistry.contains("import-menu")) {
        const importItem = cogMenuRegistry.get("import-menu", null);
        if (importItem && importItem.isDisplayed) {
            const originalIsDisplayed = importItem.isDisplayed;
            importItem.isDisplayed = (args) => {
                const config = args && args.config;
                const resModel = config && config.resModel;
                const hideGlobal = Boolean(session.hide_import_globally);
                const hideModel = Boolean(
                    resModel &&
                    session.import_restricted_models &&
                    session.import_restricted_models.includes(resModel)
                );
                if (hideGlobal || hideModel) {
                    return false;
                }
                return originalIsDisplayed(args);
            };
        }
    }
} catch (e) {
    console.error("Access Management: Failed to patch import-menu", e);
}
