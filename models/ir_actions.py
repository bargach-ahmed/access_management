# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import AccessError

class IrActionsActions(models.Model):
    _inherit = 'ir.actions.actions'

    def read(self, fields=None, load='_classic_read'):
        if not self.env.su:
            hidden_actions = self.env['access.management']._get_hidden_action_ids()
            if hidden_actions and any(act_id in hidden_actions for act_id in self.ids):
                raise AccessError(_("Access Denied: You are not authorized to view or execute this action in the current company."))
        return super().read(fields=fields, load=load)
