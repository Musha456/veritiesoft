from odoo import api, fields, models, _


class ResUsers(models.Model):
    _inherit = "res.users"

    # ---------------------------------------------------------
    # Task Counts for Smart Buttons (computed with sudo)
    # ---------------------------------------------------------

    housekeeping_task_count = fields.Integer(
        string="Housekeeping Tasks",
        compute="_compute_hotel_task_counts",
    )

    maintenance_task_count = fields.Integer(
        string="Maintenance Tasks",
        compute="_compute_hotel_task_counts",
    )

    def _compute_hotel_task_counts(self):
        Housekeeping = self.env["hotel.housekeeping"].sudo()
        Maintenance = self.env["hotel.maintenance"].sudo()
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
