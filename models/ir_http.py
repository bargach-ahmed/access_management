# -*- coding: utf-8 -*-
import time
from odoo import models
from odoo.http import request

class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        result = super().session_info()
        current_company_id = False
        if request and hasattr(request, 'httprequest') and request.httprequest.cookies.get('cids'):
            try:
                cids_raw = request.httprequest.cookies.get('cids')
                current_company_id = int(cids_raw.replace('-', ',').split(',')[0])
            except Exception:
                pass

        if not current_company_id and request and hasattr(request, 'env') and request.env:
            current_company_id = request.env.company.id

        if not current_company_id:
            current_company_id = self.env.company.id

        if result.get('cache_hashes') and 'load_menus' in result['cache_hashes']:
            result['cache_hashes']['load_menus'] = f"{result['cache_hashes']['load_menus']}_{current_company_id}_{int(time.time())}"

        if not self.env.su:
            profiles = self.env['access.management']._get_active_profiles(company_id=current_company_id)
            if profiles:
                # 1. Developer Mode policy
                if any(profiles.mapped('disable_debug_mode')):
                    result['is_admin'] = False
                    result['is_system'] = False
                    if 'user_context' in result and 'debug' in result['user_context']:
                        result['user_context']['debug'] = ''
                    if 'debug' in result:
                        result['debug'] = ''

                # 2. Global Export / Import policies
                result['hide_export_globally'] = any(profiles.mapped('hide_export_globally'))
                result['hide_import_globally'] = any(profiles.mapped('hide_import_globally'))

                # 3. Model-wise Export / Import restrictions
                export_models = set(profiles.mapped('model_line_ids').filtered(lambda m: m.hide_export).mapped('model_name'))
                export_models.update(profiles.mapped('button_line_ids').filtered(lambda b: b.hide_export).mapped('model_name'))
                result['export_restricted_models'] = [m for m in export_models if m]

                import_models = set(profiles.mapped('model_line_ids').filtered(lambda m: m.hide_import).mapped('model_name'))
                result['import_restricted_models'] = [m for m in import_models if m]

                # 4. Chatter Global & Model-wise rules
                result['hide_chatter_globally'] = any(profiles.mapped('hide_chatter_globally'))
                chatter_rules = {}
                for c_rule in profiles.mapped('chatter_line_ids'):
                    m_name = c_rule.model_name
                    if not m_name:
                        continue
                    if m_name not in chatter_rules:
                        chatter_rules[m_name] = {
                            'hide_chatter': False,
                            'hide_send_message': False,
                            'hide_log_note': False,
                            'hide_schedule_activity': False,
                        }
                    if c_rule.hide_chatter:
                        chatter_rules[m_name]['hide_chatter'] = True
                    if c_rule.hide_send_message:
                        chatter_rules[m_name]['hide_send_message'] = True
                    if c_rule.hide_log_note:
                        chatter_rules[m_name]['hide_log_note'] = True
                    if c_rule.hide_schedule_activity:
                        chatter_rules[m_name]['hide_schedule_activity'] = True

                result['chatter_rules'] = chatter_rules
            else:
                result['hide_export_globally'] = False
                result['hide_import_globally'] = False
                result['export_restricted_models'] = []
                result['import_restricted_models'] = []
                result['hide_chatter_globally'] = False
                result['chatter_rules'] = {}
        else:
            result['hide_export_globally'] = False
            result['hide_import_globally'] = False
            result['export_restricted_models'] = []
            result['import_restricted_models'] = []
            result['hide_chatter_globally'] = False
            result['chatter_rules'] = {}

        return result
