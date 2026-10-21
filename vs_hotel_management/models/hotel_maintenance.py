from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HotelMaintenance(models.Model):
    _name = "hotel.maintenance"
    _description = "Hotel Maintenance"
    _inherit = ["mail.thread", "mail.activity.mixin", "hotel.task.notification.mixin"]
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

    hotel_id = fields.Many2one(
        "hotel.hotel",
        string="Hotel",
        related="room_id.hotel_id",
        readonly=True,
    )

    building_id = fields.Many2one(
        related="room_id.building_id",
        string="Building",
        readonly=True,
    )

    floor_id = fields.Many2one(
        related="room_id.floor_id",
        string="Floor",
        readonly=True,
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
            ("1", "Low"),
            ("2", "High"),
            ("3", "Urgent"),
        ],
        string="Priority",
        default="0",
        required=True,
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

    instruction_notes = fields.Text(
        string="Instruction Notes",
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

    duration_seconds = fields.Integer(
        string="Elapsed Time (Seconds)",
        compute="_compute_duration_seconds",
    )

    @api.depends("started_at", "completed_at", "state")
    def _compute_duration_seconds(self):
        now = fields.Datetime.now()

        for task in self:
            if not task.started_at:
                task.duration_seconds = 0
                continue

            end_time = (
                task.completed_at
                if task.state == "done" and task.completed_at
                else now
                if task.state == "in_progress"
                else task.started_at
            )

            task.duration_seconds = max(
                0,
                int((end_time - task.started_at).total_seconds()),
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
        self.ensure_one()

        if self.state != "in_progress":
            raise UserError(
                _("Only maintenance tasks in progress can be completed.")
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Complete Maintenance"),
            "res_model": "hotel.task.completion.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_task_type": "maintenance",
                "default_maintenance_id": self.id,
                "default_completed_at": fields.Datetime.now(),
            },
        }

    def action_cancel(self):
        for task in self:
            if task.state in ("done", "in_progress"):
                raise UserError(
                    _(
                        "Maintenance tasks that are completed or in progress "
                        "cannot be cancelled."
                    )
                )

            if task.room_id.status in (
                    "reserved",
                    "occupied",
                    "dirty",
                    "cleaning",
            ):
                raise UserError(
                    _(
                        "This maintenance task cannot be cancelled "
                        "because room %s has status '%s'."
                    ) % (
                        task.room_id.display_name,
                        task.room_id.status,
                    )
                )

            task.state = "cancelled"
            task.room_id.status = "available"

            task._notify_assigned_user(event="cancelled")
            self._notify_whatsapp_task(event="cancelled")

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

    def unlink(self):
        for task in self:
            if task.state not in ("pending", "cancelled"):
                raise UserError(
                    _(
                        "Only pending or cancelled maintenance tasks "
                        "can be deleted. Task %s is currently %s."
                    ) % (task.display_name, task.state)
                )

        return super().unlink()