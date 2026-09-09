from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HotelMaintenance(models.Model):
    _name = "hotel.maintenance"
    _description = "Hotel Maintenance"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, scheduled_date asc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        readonly=True,
        copy=False,
        default="/",
    )

    room_id = fields.Many2one(
        "hotel.room",
        string="Room",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )

    room_category_id = fields.Many2one(
        "hotel.room.category",
        string="Room Category",
        related="room_id.room_category_id",
        store=True,
        readonly=True,
    )

    maintenance_type = fields.Selection(
        [
            ("preventive", "Preventive"),
            ("corrective", "Corrective"),
            ("breakdown", "Breakdown"),
            ("inspection", "Inspection"),
        ],
        string="Maintenance Type",
        required=True,
        default="corrective",
        tracking=True,
    )

    priority = fields.Selection(
        [
            ("0", "Normal"),
            ("1", "High"),
            ("2", "Urgent"),
        ],
        string="Priority",
        default="0",
        tracking=True,
    )

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("done", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="pending",
        required=True,
        tracking=True,
    )

    scheduled_date = fields.Datetime(
        string="Scheduled Date",
        tracking=True,
    )

    started_at = fields.Datetime(
        string="Started At",
        readonly=True,
    )

    completed_at = fields.Datetime(
        string="Completed At",
        readonly=True,
    )

    assigned_to = fields.Many2one(
        "res.users",
        string="Assigned To",
        tracking=True,
    )

    description = fields.Text(
        string="Issue / Description",
    )

    resolution = fields.Text(
        string="Resolution",
    )

    notes = fields.Text(
        string="Notes",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    assigned_to_domain = fields.Many2many(
        "res.users",
        compute="_compute_assigned_to_domain",
    )

    @api.depends()
    def _compute_assigned_to_domain(self):
        group = self.env.ref(
            "vs_hotel_management.group_hotel_maintenance_user",
            raise_if_not_found=False,
        )

        users = group.users.filtered(lambda u: u.active) if group else self.env["res.users"]

        for record in self:
            record.assigned_to_domain = users

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "hotel.maintenance"
                    )
                    or "/"
                )

        return super().create(vals_list)

    def action_start(self):
        for maintenance in self:
            if maintenance.state != "pending":
                raise UserError(
                    _(
                        "Only pending maintenance requests "
                        "can be started."
                    )
                )

            if not maintenance.assigned_to:
                raise UserError(
                    _(
                        "Please assign maintenance request %s "
                        "to a user before starting."
                    )
                    % maintenance.display_name
                )

            maintenance.write({
                "state": "in_progress",
                "started_at": fields.Datetime.now(),
            })

            if maintenance.room_id.status != "maintenance":
                maintenance.room_id.status = "maintenance"

        return True

    def action_done(self):
        for maintenance in self:
            if maintenance.state != "in_progress":
                raise UserError(
                    _(
                        "Only maintenance requests in progress "
                        "can be completed."
                    )
                )

            maintenance.write({
                "state": "done",
                "completed_at": fields.Datetime.now(),
            })

            if maintenance.room_id.status == "maintenance":
                maintenance.room_id.status = "available"

        return True

    def action_cancel(self):
        for maintenance in self:
            if maintenance.state == "done":
                raise UserError(
                    _("Completed maintenance cannot be cancelled.")
                )

            maintenance.state = "cancelled"

        return True

    def _find_active_maintenance(self, room):
        return self.search(
            [
                ("room_id", "=", room.id),
                ("state", "in", ("pending", "in_progress")),
            ],
            order="id desc",
            limit=1,
        )

    @api.model
    def create_room_maintenance(
            self,
            room,
            maintenance_type="corrective",
            description=False,
    ):
        existing = self._find_active_maintenance(room)

        if existing:
            return existing

        return self.create({
            "room_id": room.id,
            "maintenance_type": maintenance_type,
            "description": description,
            "state": "pending",
            "scheduled_date": fields.Datetime.now(),
        })

    def action_assign_task(self):
        self.ensure_one()

        if self.state not in ("pending", "in_progress"):
            raise UserError(
                _("Only pending or in-progress requests can be assigned.")
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Assign Maintenance"),
            "res_model": "hotel.task.assignment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_task_type": "maintenance",
                "default_room_id": self.room_id.id,
                "default_maintenance_id": self.id,
            },
        }