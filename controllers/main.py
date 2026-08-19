# -*- coding: utf-8 -*-
import json
from odoo import http, _
from odoo.http import request
from odoo.tools import date_utils
from odoo.exceptions import AccessError
from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.action import Action

class AccessManagementWebClient(Home):

    @http.route('/web/webclient/load_menus/<string:unique>', type='http', auth='user', methods=['GET'])
    def web_load_menus(self, unique, lang=None):
        if lang:
            request.update_context(lang=lang)

        # Clear menu ormcache so multi-company rules are evaluated on every request
        request.env['ir.ui.menu'].clear_caches()
        menus = request.env['ir.ui.menu'].load_web_menus(request.session.debug)
        body = json.dumps(menus, default=date_utils.json_default)

        # Return no-cache headers so browser never serves a stale menu tree
        response = request.make_response(body, [
            ('Content-Type', 'application/json'),
            ('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0'),
            ('Pragma', 'no-cache'),
            ('Expires', '0'),
        ])
        return response


class AccessManagementActionController(Action):

    @http.route('/web/action/load', type='json', auth="user")
    def load(self, action_id, additional_context=None):
        if not request.env.su:
            hidden_actions = set()
            if 'access.management' in request.env and hasattr(request.env['access.management'], '_get_hidden_action_ids'):
                hidden_actions = request.env['access.management']._get_hidden_action_ids()

            numeric_act_id = False
            try:
                numeric_act_id = int(action_id)
            except ValueError:
                try:
                    act_record = request.env.ref(action_id)
                    numeric_act_id = act_record.id
                except Exception:
                    pass

            if numeric_act_id and numeric_act_id in hidden_actions:
                raise AccessError(_("Access Denied: You are not authorized to view or execute this action in the current company."))

        return super().load(action_id, additional_context=additional_context)
