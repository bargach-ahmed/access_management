# -*- coding: utf-8 -*-
from lxml import etree
import time
import datetime
from odoo import models, api, _
from odoo.exceptions import UserError, AccessError
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval, time as safe_time, datetime as safe_datetime

# ==============================================================================
# TECHNICAL MODELS EXCLUSION LIST
# These models are critical to Odoo core functionality, ORM operations,
# authentication, and access management engine internals. They are excluded
# from rule evaluation to prevent infinite recursion, system lockouts, or deadlocks.
# ==============================================================================
TECHNICAL_MODELS = (
    'access.management', 'access.management.menu', 'access.management.model', 'access.management.domain',
    'access.management.field', 'access.management.button', 'access.management.button.item',
    'access.management.tab', 'access.management.tab.item',
    'access.management.chatter', 'res.users', 'res.company', 'res.groups',
    'ir.model', 'ir.model.fields', 'ir.ui.menu', 'ir.ui.view', 'ir.actions.actions',
    'ir.actions.act_window', 'ir.rule', 'ir.module.module'
)


class BaseModelOverride(models.AbstractModel):
    """ Global ORM override on 'base' that enforces Access Management policies:
    - Model-level CRUD permission checks (check_access_rights)
    - Dynamic Record-level Domain Rules (_apply_ir_rules, check_access_rule, _search)
    - View XML Arch modifications for Buttons, Tabs, Fields, and Chatter (get_views)
    - Field metadata customization (fields_get)
    """
    _inherit = 'base'

    # -------------------------------------------------------------------------
    # 1. DOMAIN EVALUATION HELPERS
    # -------------------------------------------------------------------------

    @api.model
    def _eval_domain_for_access(self, domain_str):
        """ Evaluates a dynamic domain string (e.g. "[('user_id', '=', user.id)]")
        within a safe evaluation context containing 'user', 'company', and date utilities.
        """
        if not domain_str or domain_str.strip() in ('[]', ''):
            return []
        try:
            eval_ctx = {
                'user': self.env.user,
                'company': self.env.company,
                'time': safe_time,
                'datetime': safe_datetime,
                'date': safe_datetime.date,
            }
            res = safe_eval(domain_str, eval_ctx)
            if isinstance(res, (list, tuple)):
                return list(res)
        except Exception:
            try:
                import ast
                res = ast.literal_eval(domain_str)
                if isinstance(res, (list, tuple)):
                    return list(res)
            except Exception:
                pass
        return []

    @api.model
    def _get_active_domain_rules_for_model(self, operation):
        """ Gathers active domain rules configured for this model for the given operation ('read', 'create', 'write', 'unlink').
        If no rules are directly set on a child line model (e.g. sale.order.line), it automatically inherits
        the parent model's domain rules.
        """
        if self.env.su or self._name in TECHNICAL_MODELS:
            return []
        profiles = self.env['access.management']._get_active_profiles()
        if not profiles:
            return []
        domain_rules = profiles.mapped('domain_line_ids').filtered(
            lambda d: (d.model_id.model == self._name or d.model_name == self._name) and getattr(d, f'apply_{operation}', False)
        )
        
        # Child line models (e.g. sale.order.line, account.move.line) inherit parent domain
        is_child_line = False
        if not domain_rules and ('.line' in self._name or self._name.endswith('_line')):
            parent_model = self._name.replace('.line', '').replace('_line', '')
            domain_rules = profiles.mapped('domain_line_ids').filtered(
                lambda d: (d.model_id.model == parent_model or d.model_name == parent_model) and getattr(d, f'apply_{operation}', False)
            )
            is_child_line = True

        combined = []
        for r in domain_rules:
            d = self._eval_domain_for_access(r.domain)
            if d:
                if is_child_line:
                    combined.append([(1, '=', 1)])
                else:
                    combined.append(d)
        return combined

    # -------------------------------------------------------------------------
    # 2. MODEL-LEVEL PERMISSION CHECKING (check_access_rights)
    # -------------------------------------------------------------------------

    @api.model
    def check_access_rights(self, operation, raise_exception=True):
        """ Evaluates model-level access rights:
        1. System-wide Read-Only mode: blocks 'create', 'write', 'unlink'.
        2. Direct model rules from access.management.model: perm_read, perm_create, perm_write, perm_unlink.
        3. Child line models: inherits permission from parent model.
        4. Whitelisted Menus (Show Menu = ON): automatically grants default Read access to underlying models.
        """
        if not self.env.su and self._name not in TECHNICAL_MODELS:
            profiles = self.env['access.management']._get_active_profiles()
            if profiles:
                # 1. System-wide Readonly mode
                if operation in ('create', 'write', 'unlink') and any(profiles.mapped('readonly_mode')):
                    if raise_exception:
                        raise AccessError(_("You are in Read-Only mode and cannot perform '%s' on %s.") % (operation, self._description or self._name))
                    return False

                # 2. Check direct model rule
                model_rules = profiles.mapped('model_line_ids').filtered(
                    lambda m: m.model_id.model == self._name or m.model_name == self._name
                )
                if model_rules:
                    perm_map = {
                        'read': 'perm_read',
                        'create': 'perm_create',
                        'write': 'perm_write',
                        'unlink': 'perm_unlink',
                    }
                    field_name = perm_map.get(operation)
                    if field_name:
                        is_allowed = any(getattr(m, field_name) for m in model_rules)
                        if not is_allowed:
                            if raise_exception:
                                raise AccessError(_("Access Denied: You do not have '%s' access on %s.") % (operation, self._description or self._name))
                            return False
                        else:
                            return True

                # 3. Check child relational lines (e.g. sale.order.line, account.move.line)
                if '.line' in self._name or self._name.endswith('_line'):
                    parent_model = self._name.replace('.line', '').replace('_line', '')
                    parent_rules = profiles.mapped('model_line_ids').filtered(
                        lambda m: m.model_id.model == parent_model or m.model_name == parent_model
                    )
                    if parent_rules:
                        perm_map = {
                            'read': 'perm_read',
                            'create': 'perm_create',
                            'write': 'perm_write',
                            'unlink': 'perm_unlink',
                        }
                        field_name = perm_map.get(operation)
                        if field_name and any(getattr(m, field_name) for m in parent_rules):
                            return True

                # 4. Check Show Menu Whitelist: if this model belongs to a whitelisted menu (is_show=True), grant default read access
                if operation == 'read':
                    whitelisted_models = self.env['access.management']._get_whitelisted_models_for_user()
                    if whitelisted_models:
                        if self._name in whitelisted_models:
                            return True
                        if '.line' in self._name or self._name.endswith('_line'):
                            parent_model = self._name.replace('.line', '').replace('_line', '')
                            if parent_model in whitelisted_models:
                                return True

        return super().check_access_rights(operation, raise_exception=raise_exception)

    # -------------------------------------------------------------------------
    # 3. RECORD-LEVEL RULES & DOMAIN FILTERING (_apply_ir_rules, check_access_rule)
    # -------------------------------------------------------------------------

    def _apply_ir_rules(self, query, mode='read'):
        """ Injects Access Management domain rules into SQL query where-clauses.
        Preserves global multi-company rules (rules with no group) while replacing standard group-based rules.
        """
        if self.env.su or self._name in TECHNICAL_MODELS:
            return super()._apply_ir_rules(query, mode=mode)

        profiles = self.env['access.management']._get_active_profiles()
        if profiles:
            domain_rules = self._get_active_domain_rules_for_model(mode if mode != 'unlink' else 'unlink')
            if domain_rules:
                # 1. Apply global multi-company rules (rules with no group)
                Rule = self.env['ir.rule']
                try:
                    all_rules = Rule._get_rules(self._name, mode=mode)
                    global_rules = all_rules.filtered(lambda r: not r.groups)
                    if global_rules:
                        eval_context = Rule._eval_context()
                        for r in global_rules.sudo():
                            dom = safe_eval(r.domain_force, eval_context) if r.domain_force else []
                            if dom:
                                expression.expression(expression.normalize_domain(dom), self.sudo(), self._table, query)
                except Exception:
                    pass

                # 2. Apply the custom Access Management domains
                for d in domain_rules:
                    if d and d not in ([(1, '=', 1)], [('id', '!=', 0)]):
                        try:
                            expression.expression(d, self.sudo(), self._table, query)
                        except Exception:
                            pass
                return

            # If model is in whitelisted menus (is_show=True) and no explicit domain rule was defined,
            # allow default read access across records without group-rule blocking
            if mode == 'read':
                whitelisted_models = self.env['access.management']._get_whitelisted_models_for_user()
                parent_model = self._name.replace('.line', '').replace('_line', '') if ('.line' in self._name or self._name.endswith('_line')) else self._name
                if self._name in whitelisted_models or parent_model in whitelisted_models:
                    Rule = self.env['ir.rule']
                    try:
                        all_rules = Rule._get_rules(self._name, mode=mode)
                        global_rules = all_rules.filtered(lambda r: not r.groups)
                        if global_rules:
                            eval_context = Rule._eval_context()
                            for r in global_rules.sudo():
                                dom = safe_eval(r.domain_force, eval_context) if r.domain_force else []
                                if dom:
                                    expression.expression(expression.normalize_domain(dom), self.sudo(), self._table, query)
                    except Exception:
                        pass
                    return

        return super()._apply_ir_rules(query, mode=mode)

    def _filter_access_rules_python(self, operation):
        """ Evaluates record rules in Python when memory recordsets are filtered. """
        if self.env.su or self._name in TECHNICAL_MODELS:
            return super()._filter_access_rules_python(operation)

        profiles = self.env['access.management']._get_active_profiles()
        if profiles:
            domain_rules = self._get_active_domain_rules_for_model(operation)
            if domain_rules:
                Rule = self.env['ir.rule']
                final_dom = []
                try:
                    all_rules = Rule._get_rules(self._name, mode=operation)
                    global_rules = all_rules.filtered(lambda r: not r.groups)
                    eval_context = Rule._eval_context()
                    for r in global_rules.sudo():
                        dom = safe_eval(r.domain_force, eval_context) if r.domain_force else []
                        if dom:
                            final_dom = expression.AND([final_dom, expression.normalize_domain(dom)]) if final_dom else expression.normalize_domain(dom)
                except Exception:
                    pass

                for d in domain_rules:
                    if d and d not in ([(1, '=', 1)], [('id', '!=', 0)]):
                        final_dom = expression.AND([final_dom, d]) if final_dom else d

                return self.sudo().filtered_domain(final_dom or [])

            if operation == 'read':
                whitelisted_models = self.env['access.management']._get_whitelisted_models_for_user()
                parent_model = self._name.replace('.line', '').replace('_line', '') if ('.line' in self._name or self._name.endswith('_line')) else self._name
                if self._name in whitelisted_models or parent_model in whitelisted_models:
                    Rule = self.env['ir.rule']
                    final_dom = []
                    try:
                        all_rules = Rule._get_rules(self._name, mode=operation)
                        global_rules = all_rules.filtered(lambda r: not r.groups)
                        eval_context = Rule._eval_context()
                        for r in global_rules.sudo():
                            dom = safe_eval(r.domain_force, eval_context) if r.domain_force else []
                            if dom:
                                final_dom = expression.AND([final_dom, expression.normalize_domain(dom)]) if final_dom else expression.normalize_domain(dom)
                    except Exception:
                        pass
                    return self.sudo().filtered_domain(final_dom or [])

        return super()._filter_access_rules_python(operation)

    def check_access_rule(self, operation):
        """ Validates individual records against configured Access Management domain rules. """
        if self.env.su or self._name in TECHNICAL_MODELS:
            return super().check_access_rule(operation)

        profiles = self.env['access.management']._get_active_profiles()
        if profiles:
            domain_rules = self._get_active_domain_rules_for_model(operation)
            if domain_rules:
                for d in domain_rules:
                    if d and d not in ([(1, '=', 1)], [('id', '!=', 0)]):
                        valid_ids = self.sudo().search(expression.AND([d, [('id', 'in', self.ids)]])).ids
                        if len(valid_ids) != len(self.ids):
                            raise AccessError(_("Access Denied: Record on %s does not satisfy your permitted domain rules.") % (self._description or self._name))
                return

            if operation == 'read':
                whitelisted_models = self.env['access.management']._get_whitelisted_models_for_user()
                parent_model = self._name.replace('.line', '').replace('_line', '') if ('.line' in self._name or self._name.endswith('_line')) else self._name
                if self._name in whitelisted_models or parent_model in whitelisted_models:
                    return

        return super().check_access_rule(operation)

    @api.model
    def _search(self, *args, **kwargs):
        """ Injects active Read domain rules directly into search() calls. """
        if not self.env.su and self._name not in TECHNICAL_MODELS:
            profiles = self.env['access.management']._get_active_profiles()
            if profiles:
                # 1. Model-level Read permission check
                model_rules = profiles.mapped('model_line_ids').filtered(lambda m: m.model_id.model == self._name or m.model_name == self._name)
                if model_rules and any(not m.perm_read for m in model_rules):
                    domain = [('id', '=', 0)]
                    if args:
                        args = (domain,) + args[1:]
                    else:
                        kwargs['domain'] = domain
                    return super()._search(*args, **kwargs)

                # 2. Inject Read domain rules
                domain_rules = self._get_active_domain_rules_for_model('read')
                if domain_rules:
                    domain = list(args[0]) if args else list(kwargs.get('domain') or [])
                    for d in domain_rules:
                        if d and d not in ([(1, '=', 1)], [('id', '!=', 0)]):
                            domain = expression.AND([domain, d])
                    if args:
                        args = (domain,) + args[1:]
                    else:
                        kwargs['domain'] = domain

        return super()._search(*args, **kwargs)

    # -------------------------------------------------------------------------
    # 4. VIEW XML ARCHITECTURE CUSTOMIZATION (get_views)
    # -------------------------------------------------------------------------

    @api.model
    def get_views(self, views, options=None):
        """ Intercepts get_views() to modify XML view architectures dynamically:
        - Removes/hides specific action buttons and workflow buttons
        - Hides specified notebook tabs/pages
        - Sets field attributes: invisible, readonly, required, no_open
        - Customizes chatter pane visibility and chatter action buttons
        - Disables Export, Import, Duplicate, and Archive from the Cog/Action menus
        """
        res = super().get_views(views, options=options)
        if self.env.su:
            return res

        model_name = self._name
        if model_name in TECHNICAL_MODELS:
            return res

        profiles = self.env['access.management']._get_active_profiles()
        if not profiles:
            return res

        # 1. Global Settings
        global_readonly = any(profiles.mapped('readonly_mode'))
        global_hide_export = any(profiles.mapped('hide_export_globally'))
        global_hide_import = any(profiles.mapped('hide_import_globally'))
        global_hide_chatter = any(profiles.mapped('hide_chatter_globally'))

        # 2. Model CRUD Rules
        model_rules = profiles.mapped('model_line_ids').filtered(lambda m: m.model_id.model == model_name or m.model_name == model_name)
        hide_model_create = any(not m.perm_create for m in model_rules)
        hide_model_edit = any(not m.perm_write for m in model_rules)
        hide_model_delete = any(not m.perm_unlink for m in model_rules)
        hide_model_duplicate = any(m.hide_duplicate for m in model_rules)
        hide_model_archive = any(m.hide_archive for m in model_rules)
        hide_archive = hide_model_archive

        # 3. Field Access Rules
        field_rules = profiles.mapped('field_line_ids').filtered(lambda r: r.model_id.model == model_name or r.model_name == model_name)
        invisible_field_names = set(field_rules.filtered('is_invisible').mapped('field_id.name') + field_rules.filtered('is_invisible').mapped('field_name'))
        readonly_field_names = set(field_rules.filtered('is_readonly').mapped('field_id.name') + field_rules.filtered('is_readonly').mapped('field_name'))
        required_field_names = set(field_rules.filtered('is_required').mapped('field_id.name') + field_rules.filtered('is_required').mapped('field_name'))
        no_open_field_names = set(field_rules.filtered('remove_external_link').mapped('field_id.name') + field_rules.filtered('remove_external_link').mapped('field_name'))

        # 4. Button & Action Rules
        button_rules = profiles.mapped('button_line_ids').filtered(lambda r: r.model_id.model == model_name or r.model_name == model_name)
        hide_create = global_readonly or hide_model_create or any(button_rules.mapped('hide_create'))
        hide_edit = global_readonly or hide_model_edit or any(button_rules.mapped('hide_edit'))
        hide_delete = global_readonly or hide_model_delete or any(button_rules.mapped('hide_delete'))
        hide_duplicate = global_readonly or hide_model_duplicate or any(button_rules.mapped('hide_duplicate'))
        hide_export = global_hide_export or any(m.hide_export for m in model_rules) or any(button_rules.mapped('hide_export'))
        hide_import = global_hide_import or any(m.hide_import for m in model_rules)

        specific_buttons_to_hide = set()
        for r in button_rules:
            btn_key = r.button_item_id.name or r.button_name
            if btn_key:
                specific_buttons_to_hide.add(btn_key.strip().lower())

        # 5. Tab Rules
        tab_rules = profiles.mapped('tab_line_ids').filtered(lambda r: (r.model_id.model == model_name or r.model_name == model_name) and r.is_hide)
        tabs_to_hide = set()
        for r in tab_rules:
            tab_key = r.tab_item_id.name or r.tab_name
            if tab_key:
                tabs_to_hide.add(tab_key.strip().lower())

        # 6. Chatter Rules
        chatter_rules = profiles.mapped('chatter_line_ids').filtered(lambda r: r.model_id.model == model_name or r.model_name == model_name)
        hide_chatter = global_hide_chatter or any(chatter_rules.mapped('hide_chatter'))
        hide_send_message = any(chatter_rules.mapped('hide_send_message'))
        hide_log_note = any(chatter_rules.mapped('hide_log_note'))
        hide_schedule_activity = any(chatter_rules.mapped('hide_schedule_activity'))

        # 7. Modify XML Arch for each view
        views_dict = res.get('views', {})
        for view_type, view_dict in views_dict.items():
            arch_str = view_dict.get('arch')
            if not arch_str:
                continue

            try:
                doc = etree.fromstring(arch_str.encode('utf-8'))
            except Exception:
                continue

            # A. View root attributes (create, edit, delete, duplicate, import, export)
            if hide_create:
                doc.attrib['create'] = 'false'
            if hide_edit:
                doc.attrib['edit'] = 'false'
            if hide_delete:
                doc.attrib['delete'] = 'false'
            if hide_duplicate:
                doc.attrib['duplicate'] = 'false'
            if hide_export:
                doc.attrib['export_xlsx'] = 'false'
            if hide_import:
                doc.attrib['import'] = 'false'
            if hide_archive:
                doc.attrib['archivable'] = 'false'

            # B. Specific Buttons to hide
            if specific_buttons_to_hide:
                for btn_elem in doc.iter('button'):
                    b_name = (btn_elem.attrib.get('name') or '').strip().lower()
                    b_str = (btn_elem.attrib.get('string') or '').strip().lower()
                    b_text = ''.join(btn_elem.itertext()).strip().lower()
                    
                    matched = False
                    for target in specific_buttons_to_hide:
                        if target in (b_name, b_str, b_text) or (b_name and target == b_name) or (b_str and target in b_str) or (b_text and target in b_text):
                            matched = True
                            break
                    
                    if matched:
                        btn_elem.attrib['invisible'] = '1'

            # C. Notebook Tabs (Pages) to hide
            if tabs_to_hide:
                for page_elem in doc.iter('page'):
                    p_name = (page_elem.attrib.get('name') or '').strip().lower()
                    p_str = (page_elem.attrib.get('string') or '').strip().lower()
                    if p_name in tabs_to_hide or p_str in tabs_to_hide:
                        page_elem.attrib['invisible'] = '1'

            # D. Fields modifications (Invisible, Readonly, Required, No Open, Archive)
            if invisible_field_names or readonly_field_names or required_field_names or no_open_field_names or global_readonly or hide_archive:
                for field_elem in doc.iter('field'):
                    f_name = field_elem.attrib.get('name')
                    if f_name in invisible_field_names:
                        field_elem.attrib['invisible'] = '1'
                        field_elem.attrib['column_invisible'] = '1'
                    if global_readonly or f_name in readonly_field_names:
                        field_elem.attrib['readonly'] = '1'
                    if f_name in required_field_names:
                        field_elem.attrib['required'] = '1'
                    if f_name in no_open_field_names:
                        opts = field_elem.attrib.get('options', '{}')
                        if 'no_open' not in opts:
                            opts = opts.replace('}', ", 'no_open': True, 'no_create': True}") if opts != '{}' else "{'no_open': True, 'no_create': True}"
                            field_elem.attrib['options'] = opts
                    if hide_archive and f_name in ('active', 'x_active'):
                        field_elem.attrib['readonly'] = '1'

            # E. Chatter Access Control in XML Arch
            for elem in list(doc.iter()):
                if elem.tag == 'chatter' or (elem.tag == 'div' and 'oe_chatter' in (elem.attrib.get('class') or '')):
                    if hide_chatter:
                        elem.attrib['invisible'] = '1'
                        elem.getparent().remove(elem)
                    else:
                        for child in list(elem):
                            c_name = child.attrib.get('name')
                            if hide_schedule_activity and c_name == 'activity_ids':
                                elem.remove(child)
                            elif hide_send_message and hide_log_note and c_name == 'message_ids':
                                elem.remove(child)

            view_dict['arch'] = etree.tostring(doc, encoding='unicode')

        # F. Update field metadata dictionary in res['models']
        if 'models' in res and model_name in res['models']:
            model_fields = res['models'][model_name]
            for f_name, f_props in model_fields.items():
                if f_name in invisible_field_names:
                    f_props['invisible'] = True
                if global_readonly or f_name in readonly_field_names:
                    f_props['readonly'] = True
                if f_name in required_field_names:
                    f_props['required'] = True
                if hide_archive and f_name in ('active', 'x_active'):
                    f_props['readonly'] = True

        if 'fields' in res:
            for f_name in ('active', 'x_active'):
                if hide_archive and f_name in res['fields']:
                    res['fields'][f_name]['readonly'] = True

        return res

    # -------------------------------------------------------------------------
    # 5. FIELD METADATA OVERRIDE (fields_get)
    # -------------------------------------------------------------------------

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """ Overrides fields_get() to ensure field property metadata (readonly, invisible, required)
        is communicated to web client widgets and form engines.
        """
        res = super().fields_get(allfields=allfields, attributes=attributes)
        if self.env.su:
            return res

        profiles = self.env['access.management']._get_active_profiles()
        if not profiles:
            return res

        global_readonly = any(profiles.mapped('readonly_mode'))
        if global_readonly:
            for f_props in res.values():
                f_props['readonly'] = True

        model_rules = profiles.mapped('model_line_ids').filtered(lambda m: m.model_id.model == self._name or m.model_name == self._name)
        if global_readonly or any(m.hide_archive for m in model_rules):
            for f_name in ('active', 'x_active'):
                if f_name in res:
                    res[f_name]['readonly'] = True

        field_rules = profiles.mapped('field_line_ids').filtered(lambda r: r.model_id.model == self._name or r.model_name == self._name)
        for rule in field_rules:
            fname = rule.field_id.name or rule.field_name
            if fname in res:
                if rule.is_readonly:
                    res[fname]['readonly'] = True
                if rule.is_invisible:
                    res[fname]['invisible'] = True
                if rule.is_required:
                    res[fname]['required'] = True

        return res
