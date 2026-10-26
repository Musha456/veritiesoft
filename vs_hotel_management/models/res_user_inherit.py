from odoo import api, fields, models, _


class ResUsers(models.Model):
    _inherit = "res.users"

    # ---------------------------------------------------------
    # Role Booleans (Bidirectional Sync with res.groups)
    # ---------------------------------------------------------

    is_hotel_manager = fields.Boolean(
        string="Hotel Manager",
        compute="_compute_hotel_roles",
        inverse="_inverse_hotel_manager",
        help="Designates this user as Hotel General Manager with full administrative access across all hotel operations.",
    )

    is_hotel_reservation_manager = fields.Boolean(
        string="Reservation Manager",
        compute="_compute_hotel_roles",
        inverse="_inverse_hotel_reservation_manager",
        help="Designates this user as Reservation Manager overseeing bookings and guest folios.",
    )

    is_hotel_housekeeping_manager = fields.Boolean(
        string="Housekeeping Manager",
        compute="_compute_hotel_roles",
        inverse="_inverse_hotel_housekeeping_manager",
        help="Designates this user as Housekeeping Manager overseeing room cleaning and staff assignments.",
    )

    is_hotel_maintenance_manager = fields.Boolean(
        string="Maintenance Manager",
        compute="_compute_hotel_roles",
        inverse="_inverse_hotel_maintenance_manager",
        help="Designates this user as Maintenance Manager overseeing facility repairs and technicians.",
    )

    is_hotel_housekeeping_user = fields.Boolean(
        string="Housekeeping Staff",
        compute="_compute_hotel_roles",
        inverse="_inverse_hotel_housekeeping_user",
        help="Staff member who executes room housekeeping tasks.",
    )

    is_hotel_maintenance_user = fields.Boolean(
        string="Maintenance Staff",
        compute="_compute_hotel_roles",
        inverse="_inverse_hotel_maintenance_user",
        help="Technician who executes maintenance requests.",
    )

    # ---------------------------------------------------------
    # Task Counts for Smart Buttons
    # ---------------------------------------------------------

    housekeeping_task_count = fields.Integer(
        string="Housekeeping Tasks",
        compute="_compute_hotel_task_counts",
    )

    maintenance_task_count = fields.Integer(
        string="Maintenance Tasks",
        compute="_compute_hotel_task_counts",
    )

    @api.depends("all_group_ids")
    def _compute_hotel_roles(self):
        hotel_mgr_grp = self.env.ref(
            "vs_hotel_management.group_hotel_room_manager",
            raise_if_not_found=False,
        )
        res_mgr_grp = self.env.ref(
            "vs_hotel_management.group_hotel_reservation_manager",
            raise_if_not_found=False,
        )
        hk_mgr_grp = self.env.ref(
            "vs_hotel_management.group_hotel_housekeeping_manager",
            raise_if_not_found=False,
        )
        maint_mgr_grp = self.env.ref(
            "vs_hotel_management.group_hotel_maintenance_manager",
            raise_if_not_found=False,
        )
        hk_user_grp = self.env.ref(
            "vs_hotel_management.group_hotel_housekeeping_user",
            raise_if_not_found=False,
        )
        maint_user_grp = self.env.ref(
            "vs_hotel_management.group_hotel_maintenance_user",
            raise_if_not_found=False,
        )

        for user in self:
            user_groups = user.all_group_ids
            user.is_hotel_manager = bool(hotel_mgr_grp and hotel_mgr_grp in user_groups)
            user.is_hotel_reservation_manager = bool(res_mgr_grp and res_mgr_grp in user_groups)
            user.is_hotel_housekeeping_manager = bool(hk_mgr_grp and hk_mgr_grp in user_groups)
            user.is_hotel_maintenance_manager = bool(maint_mgr_grp and maint_mgr_grp in user_groups)
            user.is_hotel_housekeeping_user = bool(hk_user_grp and hk_user_grp in user_groups)
            user.is_hotel_maintenance_user = bool(maint_user_grp and maint_user_grp in user_groups)

    def _update_group_membership(self, group_xml_id, enable):
        group = self.env.ref(group_xml_id, raise_if_not_found=False)
        if not group:
            return
        for user in self:
            if enable and group not in user.group_ids:
                user.group_ids = [(4, group.id)]
            elif not enable and group in user.group_ids:
                user.group_ids = [(3, group.id)]

    def _inverse_hotel_manager(self):
        for user in self:
            user._update_group_membership("vs_hotel_management.group_hotel_room_manager", user.is_hotel_manager)

    def _inverse_hotel_reservation_manager(self):
        for user in self:
            user._update_group_membership("vs_hotel_management.group_hotel_reservation_manager", user.is_hotel_reservation_manager)

    def _inverse_hotel_housekeeping_manager(self):
        for user in self:
            user._update_group_membership("vs_hotel_management.group_hotel_housekeeping_manager", user.is_hotel_housekeeping_manager)

    def _inverse_hotel_maintenance_manager(self):
        for user in self:
            user._update_group_membership("vs_hotel_management.group_hotel_maintenance_manager", user.is_hotel_maintenance_manager)

    def _inverse_hotel_housekeeping_user(self):
        for user in self:
            user._update_group_membership("vs_hotel_management.group_hotel_housekeeping_user", user.is_hotel_housekeeping_user)

    def _inverse_hotel_maintenance_user(self):
        for user in self:
            user._update_group_membership("vs_hotel_management.group_hotel_maintenance_user", user.is_hotel_maintenance_user)

    def _compute_hotel_task_counts(self):
        Housekeeping = self.env["hotel.housekeeping"]
        Maintenance = self.env["hotel.maintenance"]
        for user in self:
            user.housekeeping_task_count = Housekeeping.search_count([
                ("assigned_to", "=", user.id),
            ])
            user.maintenance_task_count = Maintenance.search_count([
                ("assigned_to", "=", user.id),
            ])

    def action_view_user_housekeeping_tasks(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Housekeeping Tasks"),
            "res_model": "hotel.housekeeping",
            "view_mode": "list,form",
            "domain": [("assigned_to", "=", self.id)],
            "context": {"default_assigned_to": self.id},
        }

    def action_view_user_maintenance_tasks(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Maintenance Tasks"),
            "res_model": "hotel.maintenance",
            "view_mode": "list,form",
            "domain": [("assigned_to", "=", self.id)],
            "context": {"default_assigned_to": self.id},
        }
