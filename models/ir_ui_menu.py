# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.http import request

# ==============================================================================
# MENU VISIBILITY ENGINE OVERRIDE (ir.ui.menu)
# ==============================================================================

class IrUiMenu(models.Model):
    """ Inherits 'ir.ui.menu' to enforce dynamic menu visibility:
    - Additive Whitelist: Shows selected menus on top of existing access (is_show=True)
    - Subtractive Blacklist: Hides specific menus (is_show=False)
    - Folder Pruning: Automatically prunes parent folder menus that have no visible children left
    """
    _inherit = 'ir.ui.menu'

    @api.model
    def load_menus(self, debug):
        """ Clears ORM menu cache before loading to ensure real-time multi-company updates. """
        self.clear_caches()
        return super().load_menus(debug)

    @api.model
    def get_user_roots(self):
        """ Ensures top-level application root icons for whitelisted menus (e.g. Sales, CRM)
        are included on the user's home screen / navigation bar even if standard Odoo groups are not assigned.
        """
        res = super().get_user_roots()
        if self.env.su or self.env.context.get('ir_ui_menu_no_filter'):
            return res

        access_rules = self.env['access.management']._get_active_profiles()
        if access_rules:
            menu_lines = access_rules.mapped('menu_line_ids')
            show_lines = menu_lines.filtered('is_show')
            if show_lines:
                allowed_roots = self.env['ir.ui.menu'].sudo().with_context(ir_ui_menu_no_filter=True).browse()
                for m in show_lines.mapped('menu_id').sudo():
                    root = m
                    while root.parent_id:
                        root = root.parent_id
                    allowed_roots |= root
                return res | allowed_roots
        return res

    @api.returns('self')
    def _filter_visible_menus(self):
        """ Evaluates visible menus for the current user session:
        Formula: Final Visible = (Existing Menus + Whitelisted Menus) - Blacklisted Menus
        """
        if self.env.su or self.env.context.get('ir_ui_menu_no_filter'):
            return self

        access_rules = self.env['access.management']._get_active_profiles()
        if not access_rules:
            return super()._filter_visible_menus()

        menu_lines = access_rules.mapped('menu_line_ids')
        if not menu_lines:
            return super()._filter_visible_menus()

        Menu = self.env['ir.ui.menu'].sudo().with_context(ir_ui_menu_no_filter=True)

        # Start with what the user already has access to in standard Odoo
        res = super()._filter_visible_menus()

        # 1. Add / Grant Menus (Switch ON / is_show=True): Show Selected Menus + Existing Menus
        show_lines = menu_lines.filtered('is_show')
        if show_lines:
            allowed_ids = show_lines.mapped('menu_id').ids
            whitelisted_menus = Menu.search([
                '|', ('id', 'child_of', allowed_ids), ('id', 'parent_of', allowed_ids)
            ])
            res = res | whitelisted_menus

        # 2. Hide Menus (Switch OFF / is_show=False): Remove Specified Menus
        hide_lines = menu_lines.filtered(lambda l: not l.is_show)
        if hide_lines:
            hidden_ids = hide_lines.mapped('menu_id').ids
            blacklisted_menus = Menu.search([('id', 'child_of', hidden_ids)])
            res = res - blacklisted_menus

        # 3. Prune empty folder menus (folders that have no visible children left)
        res_ids = set(res.ids)
        while True:
            parents_to_remove = set()
            for menu in res.with_context(ir_ui_menu_no_filter=True):
                if not menu.action and menu.child_id:
                    has_children = bool(set(menu.child_id.ids) & res_ids)
                    if not has_children:
                        parents_to_remove.add(menu.id)
            if not parents_to_remove:
                break
            res_ids -= parents_to_remove
            res = res.filtered(lambda m: m.id in res_ids)

        return res
