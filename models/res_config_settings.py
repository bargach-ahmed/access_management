# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    access_management_count = fields.Integer(
        string='Active Access Profiles',
        compute='_compute_access_management_stats'
    )

    def _compute_access_management_stats(self):
        count = self.env['access.management'].search_count([('active', '=', True)])
        for record in self:
            record.access_management_count = count

    def action_open_access_management(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Access Management Profiles',
            'res_model': 'access.management',
            'view_mode': 'tree,form',
            'target': 'current',
        }
