# -*- coding: utf-8 -*-
{
    'name': 'Access Management',
    'summary': 'Userwise, Groupwise & Multi-Company Access Rights, Menus, Fields, Buttons, Tabs, Chatter & Global Settings',
    'description': """
Access Management
=================
Comprehensive Access Control module for Odoo 17:
- Hide Navigation Menus and Submenus
- Action & URL Protection (Prevents direct navigation or company-switch bypass)
- Hide Fields & Set Fields Read-Only (Form, List views, and ORM write protection)
- Hide Buttons & View Actions (Create, Edit, Delete, Duplicate, Export, Custom Buttons by Name/Label)
- Hide Form Notebook Tabs / Pages (by Name or Label)
- Chatter Access Control (Hide Entire Chatter, Send Message, Log Note, Schedule Activities)
- Global Settings & Policies (System-wide Read-Only mode, Disable Developer Mode, Global Export/Import restrictions)
- Multi-Company & User Group Scoping
- Interactive Profile Dashboard with Smart Counters & General Settings Panel
    """,
    'author': 'Internship Project',
    'category': 'Administration',
    'version': '17.0.2.7.0',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/access_management_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'access_management/static/src/js/chatter_patch.js',
            'access_management/static/src/js/access_management_patch.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
