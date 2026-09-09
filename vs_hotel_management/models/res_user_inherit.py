from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    is_hotel_housekeeping_user = fields.Boolean(
        string="Hotel Housekeeping User",
        compute="_compute_hotel_role",
    )

    is_hotel_maintenance_user = fields.Boolean(
        string="Hotel Maintenance User",
        compute="_compute_hotel_role",
    )

    @api.depends("groups_id")
    def _compute_hotel_role(self):
        housekeeping_group = self.env.ref(
            "vs_hotel_management.group_hotel_housekeeping_user",
            raise_if_not_found=False,
        )

        maintenance_group = self.env.ref(
            "vs_hotel_management.group_hotel_maintenance_user",
            raise_if_not_found=False,
        )

        for user in self:
            user.is_hotel_housekeeping_user = bool(
                housekeeping_group
                and housekeeping_group in user.groups_id
            )

            user.is_hotel_maintenance_user = bool(
                maintenance_group
                and maintenance_group in user.groups_id
            )