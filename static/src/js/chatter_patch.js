/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Chatter } from "@mail/core/web/chatter";
import { session } from "@web/session";
import { useEffect } from "@odoo/owl";

patch(Chatter.prototype, {
    setup() {
        super.setup(...arguments);

        useEffect(
            () => {
                if (!this.rootRef.el) {
                    return;
                }
                const modelName = this.props.threadModel || (this.props.thread && this.props.thread.model);
                const rules = session.chatter_rules && session.chatter_rules[modelName];

                if (session.hide_chatter_globally || (rules && rules.hide_chatter)) {
                    this.rootRef.el.style.display = "none";
                    return;
                }

                if (rules) {
                    if (rules.hide_send_message) {
                        const sendBtn = this.rootRef.el.querySelector(".o-mail-Chatter-sendMessage");
                        if (sendBtn) {
                            sendBtn.style.display = "none";
                        }
                    }
                    if (rules.hide_log_note) {
                        const logBtn = this.rootRef.el.querySelector(".o-mail-Chatter-logNote");
                        if (logBtn) {
                            logBtn.style.display = "none";
                        }
                    }
                    if (rules.hide_schedule_activity) {
                        const actBtn = this.rootRef.el.querySelector(".o-mail-Chatter-activity");
                        if (actBtn) {
                            actBtn.style.display = "none";
                        }
                        const actList = this.rootRef.el.querySelector(".o-mail-ActivityList");
                        if (actList) {
                            actList.style.display = "none";
                        }
                    }
                }
            },
            () => [this.rootRef.el, this.props.threadModel, this.state.thread]
        );
    }
});
