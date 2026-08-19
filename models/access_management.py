# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.http import request

# ==============================================================================
# MAIN ACCESS MANAGEMENT PROFILE MODEL
# ==============================================================================

class AccessManagement(models.Model):
    """ Central Access Management Profile that binds users, groups, and companies
    with granular security rules for menus, models, fields, buttons, tabs, and chatter.
    """
    _name = 'access.management'
    _description = 'Access Management Profile'
    _order = 'name'

    # Profile Header Information
    name = fields.Char(string='Access Profile Name', required=True, help="Descriptive name for this access policy (e.g. Sales Rep Policy).")
    active = fields.Boolean(string='Active', default=True, help="Toggle to enable or archive this access profile.")
    
    # Target Assignments
    user_ids = fields.Many2many('res.users', 'access_management_res_users_rel', 'access_management_id', 'user_id', string='Users', help="Specific users to whom this profile applies.")
    group_ids = fields.Many2many('res.groups', 'access_management_res_groups_rel', 'access_management_id', 'group_id', string='User Groups', help="Security groups whose members inherit this profile.")
    company_ids = fields.Many2many('res.company', 'access_management_res_company_rel', 'access_management_id', 'company_id', string='Companies', help="Scope this profile to specific companies. Leave empty for all companies (Global).")

    # Global System-Wide Settings
    disable_debug_mode = fields.Boolean(string='Disable Developer Mode', default=False, help="Blocks developer tools and debug mode URLs for target users.")
    readonly_mode = fields.Boolean(string='Read-Only Mode (System Wide)', default=False, help="Places target users in full read-only mode across the entire system.")
    hide_export_globally = fields.Boolean(string='Hide Export Globally', default=False, help="Disables the Export option across all models system-wide.")
    hide_import_globally = fields.Boolean(string='Hide Import Globally', default=False, help="Disables the Import action across all models system-wide.")
    hide_chatter_globally = fields.Boolean(string='Hide Chatter Globally', default=False, help="Completely removes the chatter widget from all form views system-wide.")

    # Rule Relationships (Notebook Tabs)
    menu_line_ids = fields.One2many('access.management.menu', 'access_management_id', string='Menu Rules')
    model_line_ids = fields.One2many('access.management.model', 'access_management_id', string='Model Rules (CRUD & Actions)')
    domain_line_ids = fields.One2many('access.management.domain', 'access_management_id', string='Domain Rules (Records)')
    field_line_ids = fields.One2many('access.management.field', 'access_management_id', string='Field Rules')
    button_line_ids = fields.One2many('access.management.button', 'access_management_id', string='Button Rules')
    tab_line_ids = fields.One2many('access.management.tab', 'access_management_id', string='Form Tab Rules')
    chatter_line_ids = fields.One2many('access.management.chatter', 'access_management_id', string='Chatter Rules')

    # Stat Button Counters
    hide_menu_count = fields.Integer(string='Menus', compute='_compute_stats')
    model_rule_count = fields.Integer(string='Model Rules', compute='_compute_stats')
    domain_rule_count = fields.Integer(string='Domain Rules', compute='_compute_stats')
    field_rule_count = fields.Integer(string='Field Rules', compute='_compute_stats')
    button_rule_count = fields.Integer(string='Button Rules', compute='_compute_stats')
    tab_rule_count = fields.Integer(string='Tab Rules', compute='_compute_stats')
    chatter_rule_count = fields.Integer(string='Chatter Rules', compute='_compute_stats')

    total_users_count = fields.Integer(string='Users Count', compute='_compute_stats')
    total_companies_count = fields.Integer(string='Companies Count', compute='_compute_stats')
    total_models_count = fields.Integer(string='Models Count', compute='_compute_stats')
    total_domains_count = fields.Integer(string='Domains Count', compute='_compute_stats')
    total_fields_count = fields.Integer(string='Fields Count', compute='_compute_stats')
    total_buttons_count = fields.Integer(string='Buttons Count', compute='_compute_stats')
    total_tabs_count = fields.Integer(string='Tabs Count', compute='_compute_stats')
    total_chatters_count = fields.Integer(string='Chatters Count', compute='_compute_stats')
    total_menus_count = fields.Integer(string='Menus Count', compute='_compute_stats')

    @api.depends('user_ids', 'company_ids', 'menu_line_ids', 'model_line_ids', 'domain_line_ids', 'field_line_ids', 'button_line_ids', 'tab_line_ids', 'chatter_line_ids')
    def _compute_stats(self):
        """ Computes live stat counts for stat buttons on the profile form view. """
        for rec in self:
            rec.hide_menu_count = len(rec.menu_line_ids)
            rec.model_rule_count = len(rec.model_line_ids)
            rec.domain_rule_count = len(rec.domain_line_ids)
            rec.field_rule_count = len(rec.field_line_ids)
            rec.button_rule_count = len(rec.button_line_ids)
            rec.tab_rule_count = len(rec.tab_line_ids)
            rec.chatter_rule_count = len(rec.chatter_line_ids)

            rec.total_users_count = len(rec.user_ids)
            rec.total_companies_count = len(rec.company_ids)
            rec.total_models_count = len(rec.model_line_ids)
            rec.total_domains_count = len(rec.domain_line_ids)
            rec.total_fields_count = len(rec.field_line_ids)
            rec.total_buttons_count = len(rec.button_line_ids)
            rec.total_tabs_count = len(rec.tab_line_ids)
            rec.total_chatters_count = len(rec.chatter_line_ids)
            rec.total_menus_count = len(rec.menu_line_ids)

    # -------------------------------------------------------------------------
    # STAT BUTTON ACTIONS
    # -------------------------------------------------------------------------
    def action_view_menus(self):
        return True

    def action_view_models(self):
        return True

    def action_view_domains(self):
        return True

    def action_view_fields(self):
        return True

    def action_view_buttons(self):
        return True

    def action_view_tabs(self):
        return True

    def action_view_chatter(self):
        return True

    # -------------------------------------------------------------------------
    # CORE ENGINE: ACTIVE PROFILE & MODEL RESOLUTION
    # -------------------------------------------------------------------------

    @api.model
    def _get_active_profiles(self, user=None, company_id=None):
        """ Finds all active Access Management profiles applicable to the given user and current company context.
        Matches if:
        - The user is in `user_ids` OR in one of `group_ids`
        - The profile is global (company_ids empty) OR contains the active company
        """
        if self.env.su and not user:
            return self.browse()

        user = user or self.env.user
        user_group_ids = user.groups_id.ids or [0]

        if not company_id:
            # Extract company from HTTP session cookie if available
            if request and hasattr(request, 'httprequest') and request.httprequest.cookies.get('cids'):
                try:
                    cids_raw = request.httprequest.cookies.get('cids')
                    company_id = int(cids_raw.replace('-', ',').split(',')[0])
                except Exception:
                    pass

            if not company_id and request and hasattr(request, 'env') and request.env:
                company_id = request.env.company.id

            if not company_id:
                company_id = self.env.company.id or (user.company_id.id if user.company_id else False)

        c_filter = [company_id] if company_id else [self.env.company.id] if self.env.company else []

        domain = [
            ('active', '=', True),
            '|',
                ('user_ids', 'in', [user.id]),
                ('group_ids', 'in', user_group_ids),
        ]
        if c_filter:
            domain += [
                '|',
                    ('company_ids', '=', False),
                    ('company_ids', 'in', c_filter)
            ]

        return self.sudo().search(domain)

    @api.model
    def _get_whitelisted_models_for_user(self, user=None, company_id=None):
        """ Resolves all models that belong to menus switched to is_show=True (Show Menu),
        and automatically includes all relational co-models (Many2one, Many2many, One2many)
        so that form views and relational dropdowns (e.g. crm.tag, partner, pricelist)
        load seamlessly with default Read access.
        """
        profiles = self._get_active_profiles(user=user, company_id=company_id)
        if not profiles:
            return set()

        menu_lines = profiles.mapped('menu_line_ids')
        show_lines = menu_lines.filtered('is_show')
        if not show_lines:
            return set()

        allowed_menu_ids = show_lines.mapped('menu_id').ids
        Menu = self.env['ir.ui.menu'].sudo().with_context(ir_ui_menu_no_filter=True)
        full_allowed = Menu.search([('id', 'child_of', allowed_menu_ids)])

        whitelisted_models = set()
        for menu in full_allowed:
            if menu.action:
                try:
                    action_record = menu.action
                    if hasattr(action_record, 'res_model') and action_record.res_model:
                        whitelisted_models.add(action_record.res_model)
                    elif isinstance(action_record, str) and ',' in action_record:
                        act_model, act_id = action_record.split(',')
                        act_obj = self.env[act_model].sudo().browse(int(act_id))
                        if hasattr(act_obj, 'res_model') and act_obj.res_model:
                            whitelisted_models.add(act_obj.res_model)
                except Exception:
                    pass

        # Automatically include relational co-models for all whitelisted models so relational fields
        # (e.g. crm.tag, utm.source, payment terms, order lines) can be read without access errors
        all_models_with_relations = set(whitelisted_models)
        for model_name in whitelisted_models:
            if model_name in self.env:
                try:
                    model_obj = self.env[model_name]
                    for field_name, field in model_obj._fields.items():
                        if field.relational and field.comodel_name:
                            all_models_with_relations.add(field.comodel_name)
                except Exception:
                    pass

        return all_models_with_relations

    @api.model
    def _get_hidden_action_ids(self, user=None, company_id=None):
        """ Returns all action IDs linked to explicitly hidden menus (is_show=False)
        to protect against direct URL parameter manipulation.
        """
        profiles = self._get_active_profiles(user=user, company_id=company_id)
        if not profiles:
            return set()

        hidden_action_ids = set()
        menu_lines = profiles.mapped('menu_line_ids')
        Menu = self.env['ir.ui.menu'].sudo().with_context(ir_ui_menu_no_filter=True)

        # Blacklist (Switch OFF / is_show=False): block action IDs for explicitly hidden menus
        hide_lines = menu_lines.filtered(lambda l: not l.is_show)
        if hide_lines:
            hidden_ids = hide_lines.mapped('menu_id').ids
            all_hidden_menus = Menu.search([('id', 'child_of', hidden_ids)])
            for menu in all_hidden_menus:
                if menu.action:
                    try:
                        act_id = int(menu.action.id if hasattr(menu.action, 'id') else menu.action.split(',')[1])
                        hidden_action_ids.add(act_id)
                    except Exception:
                        pass

        return hidden_action_ids

    @api.model
    def _get_restricted_companies_for_model(self, model_name, user=None):
        """ Identifies unauthorized companies for a specific model when company scoping is active. """
        profiles = self._get_active_profiles(user=user)
        if not profiles:
            return set()
        model_rules = profiles.mapped('model_line_ids').filtered(lambda m: m.model_id.model == model_name or m.model_name == model_name)
        if model_rules:
            allowed_companies = set()
            for p in profiles:
                if p.company_ids:
                    allowed_companies.update(p.company_ids.ids)
            if allowed_companies:
                all_user_companies = set(self.env.user.company_ids.ids)
                return all_user_companies - allowed_companies
        return set()

    # -------------------------------------------------------------------------
    # ORM CACHE INVALIDATION
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        self.env.registry.clear_cache()
        return res

    def write(self, vals):
        res = super().write(vals)
        self.env.registry.clear_cache()
        return res

    def unlink(self):
        res = super().unlink()
        self.env.registry.clear_cache()
        return res
