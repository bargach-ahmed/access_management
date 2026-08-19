# -*- coding: utf-8 -*-
from lxml import etree
from odoo import models, fields, api

# ==============================================================================
# 1. MENU ACCESS RULES
# ==============================================================================

class AccessManagementMenu(models.Model):
    """ Configures menu visibility rules per access profile.
    
    Toggling `is_show`:
    - False (Default / OFF): Hides the specified menu and its submenus (Blacklist mode).
    - True (ON): Adds the menu to the user's view (Additive Whitelist) and automatically
      grants default Read access on its underlying models and relational co-models.
    """
    _name = 'access.management.menu'
    _description = 'Access Management Menu Rule'

    access_management_id = fields.Many2one(
        'access.management',
        string='Access Profile',
        required=True,
        ondelete='cascade',
        help="Access profile to which this menu rule belongs."
    )
    menu_id = fields.Many2one(
        'ir.ui.menu',
        string='Target Menu',
        required=True,
        ondelete='cascade',
        help="The menu item to configure (e.g. Sales, Accounting, Invoicing)."
    )
    parent_id = fields.Many2one(
        related='menu_id.parent_id',
        string='Parent Menu',
        readonly=True,
        store=True,
        help="Parent root or category of the selected menu."
    )
    is_show = fields.Boolean(
        string='Show Menu',
        default=False,
        help="By default (OFF), this menu is hidden. Switch ON to show this menu on top of existing access and automatically grant default Read access to its models."
    )


# ==============================================================================
# 2. DISCOVERED BUTTON & TAB HELPER MODELS
# ==============================================================================

class AccessManagementButtonItem(models.Model):
    """ Stores buttons automatically discovered from a model's form views.
    Enables administrators to select buttons from a dropdown without knowing technical names.
    """
    _name = 'access.management.button.item'
    _description = 'Discovered Model Button Item'
    _order = 'name'
    _rec_name = 'display_name'

    model_id = fields.Many2one(
        'ir.model',
        string='Target Model',
        required=True,
        ondelete='cascade',
        index=True,
        help="Model whose view contains this button."
    )
    name = fields.Char(string='Technical Name / Key', required=True, help="Technical name attribute or string key of the button.")
    display_name = fields.Char(string='Button Name', required=True, help="Human-friendly button label displayed in the dropdown.")

    _sql_constraints = [
        ('model_button_uniq', 'unique(model_id, name)', 'Button item must be unique per model.')
    ]


class AccessManagementTabItem(models.Model):
    """ Stores notebook tabs/pages automatically discovered from a model's form views.
    Enables administrators to select tabs from a dropdown without knowing technical names.
    """
    _name = 'access.management.tab.item'
    _description = 'Discovered Model Tab Item'
    _order = 'name'
    _rec_name = 'display_name'

    model_id = fields.Many2one(
        'ir.model',
        string='Target Model',
        required=True,
        ondelete='cascade',
        index=True,
        help="Model whose form view contains this notebook page."
    )
    name = fields.Char(string='Technical Name / Key', required=True, help="Technical name attribute or string title of the tab.")
    display_name = fields.Char(string='Tab Title', required=True, help="Human-friendly tab label displayed in the dropdown.")

    _sql_constraints = [
        ('model_tab_uniq', 'unique(model_id, name)', 'Tab item must be unique per model.')
    ]


# ==============================================================================
# 3. MODEL CRUD & ACTION RULES
# ==============================================================================

class AccessManagementModel(models.Model):
    """ Defines model-level CRUD permissions and view action restrictions.
    Controls perm_read, perm_create, perm_write, perm_unlink, and hides Export/Import/Duplicate/Archive.
    """
    _name = 'access.management.model'
    _description = 'Access Management Model CRUD Rule'

    access_management_id = fields.Many2one(
        'access.management',
        string='Access Profile',
        required=True,
        ondelete='cascade'
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Target Model',
        required=True,
        ondelete='cascade',
        help="The database model to restrict or permit (e.g. sale.order, res.partner)."
    )
    model_name = fields.Char(related='model_id.model', string='Model Technical Name', readonly=True, store=True)

    # Core CRUD Permission Flags
    perm_read = fields.Boolean(string='Read', default=True, help="Allow reading records of this model.")
    perm_create = fields.Boolean(string='Create', default=True, help="Allow creating new records.")
    perm_write = fields.Boolean(string='Write (Edit)', default=True, help="Allow modifying/editing existing records.")
    perm_unlink = fields.Boolean(string='Delete', default=True, help="Allow deleting records.")

    # Action Restrictions
    hide_export = fields.Boolean(string='Hide Export', default=False, help="Hides the Export action button and blocks backend export_data().")
    hide_import = fields.Boolean(string='Hide Import', default=False, help="Hides the Import button and blocks backend load().")
    hide_duplicate = fields.Boolean(string='Hide Duplicate', default=False, help="Hides Duplicate from Action menu and blocks backend copy().")
    hide_archive = fields.Boolean(string='Hide Archive', default=False, help="Hides Archive / Unarchive from Action menu and blocks toggle_active().")


# ==============================================================================
# 4. DOMAIN / RECORD RULES
# ==============================================================================

class AccessManagementDomain(models.Model):
    """ Defines record-level Python/Odoo domain filter expressions per operation.
    Applies specifically to Read, Create, Write, or Delete operations.
    """
    _name = 'access.management.domain'
    _description = 'Access Management Domain Rule'

    access_management_id = fields.Many2one(
        'access.management',
        string='Access Profile',
        required=True,
        ondelete='cascade'
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Target Model',
        required=True,
        ondelete='cascade',
        help="The database model on which to apply the domain filter."
    )
    model_name = fields.Char(related='model_id.model', string='Model Technical Name', readonly=True, store=True)
    domain = fields.Char(
        string='Domain Filter Expression',
        required=True,
        default="[]",
        help="Odoo domain filter (e.g. [('user_id', '=', user.id)] or [('company_id', '=', company.id)])."
    )

    # Operation-specific applicability flags
    apply_read = fields.Boolean(string='Read', default=True, help="Filter records visible in search, list, and form views.")
    apply_create = fields.Boolean(string='Create', default=True, help="Validate records upon creation.")
    apply_write = fields.Boolean(string='Write', default=True, help="Restrict modifications to records matching this domain.")
    apply_unlink = fields.Boolean(string='Delete', default=True, help="Restrict deleting records matching this domain.")


# ==============================================================================
# 5. FIELD-LEVEL ACCESS RULES
# ==============================================================================

class AccessManagementField(models.Model):
    """ Controls field visibility, read-only status, required state, and Many2one link behavior. """
    _name = 'access.management.field'
    _description = 'Access Management Field Rule'

    access_management_id = fields.Many2one(
        'access.management',
        string='Access Profile',
        required=True,
        ondelete='cascade'
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Target Model',
        required=True,
        ondelete='cascade'
    )
    model_name = fields.Char(related='model_id.model', string='Model Technical Name', readonly=True, store=True)
    field_id = fields.Many2one(
        'ir.model.fields',
        string='Target Field',
        required=True,
        ondelete='cascade',
        domain="[('model_id', '=', model_id)]",
        help="The specific field to restrict on the target model."
    )
    field_name = fields.Char(related='field_id.name', string='Field Technical Name', readonly=True, store=True)
    is_invisible = fields.Boolean(string='Hide Field', default=False, help="Hides field from views completely.")
    is_readonly = fields.Boolean(string='Read-Only', default=False, help="Makes field read-only and blocks write modifications.")
    is_required = fields.Boolean(string='Required', default=False, help="Forces field to be mandatory before saving.")
    remove_external_link = fields.Boolean(string='Remove External Link', default=False, help="Disables clickable external link popup on Many2one fields (no_open).")


# ==============================================================================
# 6. BUTTON & ACTION RULES
# ==============================================================================

class AccessManagementButton(models.Model):
    """ Hides specific action buttons or workflow buttons on views. """
    _name = 'access.management.button'
    _description = 'Access Management Button & Action Rule'

    access_management_id = fields.Many2one(
        'access.management',
        string='Access Profile',
        required=True,
        ondelete='cascade'
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Target Model',
        required=True,
        ondelete='cascade'
    )
    model_name = fields.Char(related='model_id.model', string='Model Technical Name', readonly=True, store=True)

    button_item_id = fields.Many2one(
        'access.management.button.item',
        string='Select Button',
        domain="[('model_id', '=', model_id)]",
        help="Select a button discovered from this model's views."
    )
    
    hide_create = fields.Boolean(string='Hide Create', default=False, help="Hides the Create / New button on views.")
    hide_edit = fields.Boolean(string='Hide Edit', default=False, help="Hides the Edit button on form views.")
    hide_delete = fields.Boolean(string='Hide Delete', default=False, help="Hides the Delete action from views.")
    hide_duplicate = fields.Boolean(string='Hide Duplicate', default=False, help="Hides the Duplicate action from views.")
    hide_export = fields.Boolean(string='Hide Export', default=False, help="Hides the Export action from views.")
    
    button_name = fields.Char(
        string='Button Name or Label',
        help="Visible button string label (e.g. Confirm, Cancel, Send by Email) or technical name (e.g. action_confirm)."
    )

    @api.onchange('model_id')
    def _onchange_model_id_extract_buttons(self):
        """ Dynamically inspects form view XML architectures when a model is selected,
        discovering all buttons and storing them in access.management.button.item for dropdown selection.
        """
        if self.model_id:
            self._extract_buttons_for_model(self.model_id)

    @api.onchange('button_item_id')
    def _onchange_button_item_id(self):
        """ Syncs the chosen dropdown button item with the button_name key. """
        if self.button_item_id:
            self.button_name = self.button_item_id.name

    @api.model
    def _extract_buttons_for_model(self, model_rec):
        """ Parses all form views of the target model and indexes buttons. """
        if not model_rec or not model_rec.model:
            return
        views = self.env['ir.ui.view'].sudo().search([('model', '=', model_rec.model), ('type', '=', 'form')])
        ButtonItem = self.env['access.management.button.item'].sudo()
        existing_names = set(ButtonItem.search([('model_id', '=', model_rec.id)]).mapped('name'))

        for view in views:
            arch = view.arch
            if not arch:
                continue
            try:
                doc = etree.fromstring(arch.encode('utf-8'))
            except Exception:
                continue

            for btn in doc.iter('button'):
                b_name = btn.attrib.get('name')
                b_str = btn.attrib.get('string')
                b_icon = btn.attrib.get('icon')

                display_name = b_str or b_name
                if b_str and b_name and b_str != b_name:
                    display_name = f"{b_str} ({b_name})"
                elif not display_name and b_icon:
                    display_name = f"Button ({b_icon})"

                key = b_name or b_str
                if key and key not in existing_names:
                    ButtonItem.create({
                        'model_id': model_rec.id,
                        'name': key,
                        'display_name': display_name or key
                    })
                    existing_names.add(key)


# ==============================================================================
# 7. FORM TAB (NOTEBOOK PAGE) RULES
# ==============================================================================

class AccessManagementTab(models.Model):
    """ Hides notebook tabs/pages on form views (e.g. Internal Notes, Order Lines, Other Info). """
    _name = 'access.management.tab'
    _description = 'Access Management Notebook Tab Rule'

    access_management_id = fields.Many2one(
        'access.management',
        string='Access Profile',
        required=True,
        ondelete='cascade'
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Target Model',
        required=True,
        ondelete='cascade'
    )
    model_name = fields.Char(related='model_id.model', string='Model Technical Name', readonly=True, store=True)

    tab_item_id = fields.Many2one(
        'access.management.tab.item',
        string='Select Form Tab',
        domain="[('model_id', '=', model_id)]",
        help="Select a notebook tab/page discovered from this model's form views."
    )

    tab_name = fields.Char(
        string='Notebook Page Name or Label',
        help="Visible string title of the notebook page (e.g. Internal Notes, Extra Info) or technical name attribute."
    )
    is_hide = fields.Boolean(string='Hide Tab', default=True, help="Hides the tab from the form view.")

    @api.onchange('model_id')
    def _onchange_model_id_extract_tabs(self):
        """ Dynamically inspects form view XML architectures when a model is selected,
        discovering all notebook tabs and storing them in access.management.tab.item for dropdown selection.
        """
        if self.model_id:
            self._extract_tabs_for_model(self.model_id)

    @api.onchange('tab_item_id')
    def _onchange_tab_item_id(self):
        """ Syncs the chosen dropdown tab item with the tab_name key. """
        if self.tab_item_id:
            self.tab_name = self.tab_item_id.name

    @api.model
    def _extract_tabs_for_model(self, model_rec):
        """ Parses all form views of the target model and indexes notebook pages. """
        if not model_rec or not model_rec.model:
            return
        views = self.env['ir.ui.view'].sudo().search([('model', '=', model_rec.model), ('type', '=', 'form')])
        TabItem = self.env['access.management.tab.item'].sudo()
        existing_names = set(TabItem.search([('model_id', '=', model_rec.id)]).mapped('name'))

        for view in views:
            arch = view.arch
            if not arch:
                continue
            try:
                doc = etree.fromstring(arch.encode('utf-8'))
            except Exception:
                continue

            for page in doc.iter('page'):
                p_name = page.attrib.get('name')
                p_str = page.attrib.get('string')

                display_name = p_str or p_name
                if p_str and p_name and p_str != p_name:
                    display_name = f"{p_str} ({p_name})"

                key = p_name or p_str
                if key and key not in existing_names:
                    TabItem.create({
                        'model_id': model_rec.id,
                        'name': key,
                        'display_name': display_name or key
                    })
                    existing_names.add(key)


# ==============================================================================
# 8. CHATTER ACCESS RULES
# ==============================================================================

class AccessManagementChatter(models.Model):
    """ Controls chatter widget and button visibility (Send Message, Log Note, Schedule Activities) per model. """
    _name = 'access.management.chatter'
    _description = 'Access Management Chatter Rule'

    access_management_id = fields.Many2one(
        'access.management',
        string='Access Profile',
        required=True,
        ondelete='cascade'
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Target Model',
        required=True,
        ondelete='cascade'
    )
    model_name = fields.Char(related='model_id.model', string='Model Technical Name', readonly=True, store=True)
    
    hide_chatter = fields.Boolean(string='Hide Entire Chatter', default=False, help="Hides the whole chatter pane for this model.")
    hide_send_message = fields.Boolean(string='Hide Send Message', default=False, help="Hides the Send message button.")
    hide_log_note = fields.Boolean(string='Hide Log Note', default=False, help="Hides the Log note button.")
    hide_schedule_activity = fields.Boolean(string='Hide Activities', default=False, help="Hides the Schedule Activity button.")
