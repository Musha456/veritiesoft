# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import AccessError


class IrActionsActWindow(models.Model):
    _inherit = 'ir.actions.act_window'

    def _get_action_dict(self):
        """
        Enforce group-based access control when window actions are loaded
        directly via URL (/web/action/load, direct bookmarks, or _for_xml_id).
        If the action has group_ids configured and the current user does not
        belong to any of those groups (and is not a system administrator),
        block access with an AccessError.
        """
        self.ensure_one()
        user = self.env.user
        # Root user (ID 1) and System Administrators bypass group restrictions
        if user.id != 1 and not user.has_group('base.group_system'):
            if self.group_ids and not (self.group_ids & user.all_group_ids):
                raise AccessError(_("You are not allowed to access this document or page."))
        return super()._get_action_dict()
