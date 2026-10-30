from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class HotelHousekeeping(models.Model):
    _name = "hotel.housekeeping"
    _description = "Hotel Housekeeping"
    _inherit = ["mail.thread", "mail.activity.mixin", "hotel.task.notification.mixin"]
    _order = "priority desc, scheduled_date asc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
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

    reservation_id = fields.Many2one(
        "hotel.reservation",
        string="Reservation",
        readonly=True,
        index=True,
    )

    room_booking_id = fields.Many2one(
        "hotel.room.booking",
        string="Room Booking",
        readonly=True,
        index=True,
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
        related="room_id.room_category_id",
        string="Room Category",
        store=True,
        readonly=True,
    )

    housekeeping_type = fields.Selection(
        [
            ("checkout", "Checkout Cleaning"),
            ("stayover", "Stayover Cleaning"),
            ("deep", "Deep Cleaning"),
            ("maintenance", "Maintenance"),
        ],
        string="Housekeeping Type",
        required=True,
        default="checkout",
        tracking=True,
    )

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        required=True,
        default="pending",
        tracking=True,
        copy=False,
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

    scheduled_date = fields.Datetime(
        string="Scheduled Date",
        default=fields.Datetime.now,
        required=True,
        index=True,
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

    whatsapp_log_count = fields.Integer(
        string="WhatsApp Logs",
        compute="_compute_whatsapp_log_count",
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

    def _compute_whatsapp_log_count(self):
        Log = self.env["hotel.whatsapp.log"]
        for task in self:
            task.whatsapp_log_count = Log.search_count([
                ("task_reference", "=", f"{task._name},{task.id}")
            ])

    def action_view_whatsapp_logs(self):
        self.ensure_one()
        return {
            "name": _("WhatsApp Notifications"),
            "type": "ir.actions.act_window",
            "res_model": "hotel.whatsapp.log",
            "view_mode": "list,form",
            "domain": [("task_reference", "=", f"{self._name},{self.id}")],
            "context": {
                "default_task_reference": f"{self._name},{self.id}",
                "default_task_type": "housekeeping",
                "default_company_id": self.company_id.id,
            },
        }

    @api.depends()
    def _compute_assigned_to_domain(self):
        group = self.env.ref(
            "vs_hotel_management.group_hotel_housekeeping_user",
            raise_if_not_found=False,
        )

        users = group.user_ids.filtered(lambda u: u.active) if group else self.env["res.users"]

        for record in self:
            record.assigned_to_domain = users

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "hotel.housekeeping"
                ) or "/"

        return super().create(vals_list)

    def _find_active_task(self, room):
        return self.search(
            [
                ("room_id", "=", room.id),
                ("state", "in", ("pending", "in_progress")),
            ],
            limit=1,
        )

    @api.model
    def create_checkout_task(
            self,
            room,
            reservation=None,
            room_booking=None,
            assigned_to=None,
            instruction_notes=None,
            auto_start=False,
    ):
        existing = self._find_active_task(room)

        user_id = assigned_to.id if hasattr(assigned_to, 'id') else (int(assigned_to) if assigned_to else False)
        instructions = instruction_notes or _("Checkout room housekeeping cleaning")

        if existing:
            vals = {}
            if user_id and not existing.assigned_to:
                vals["assigned_to"] = user_id
            if instructions and not existing.instruction_notes:
                vals["instruction_notes"] = instructions
            if vals:
                existing.write(vals)
            if user_id:
                existing._notify_assigned_user(event="assigned")
                existing._notify_whatsapp_task(event="assigned")
                existing._notify_sms_task(event="assigned")
            if auto_start and existing.state == "pending" and existing.assigned_to:
                existing.action_start()
            return existing

        task = self.create({
            "room_id": room.id,
            "reservation_id": reservation.id if reservation else False,
            "room_booking_id": (
                room_booking.id if room_booking else False
            ),
            "housekeeping_type": "checkout",
            "state": "pending",
            "scheduled_date": fields.Datetime.now(),
            "assigned_to": user_id,
            "instruction_notes": instructions,
        })

        if user_id:
            task._notify_assigned_user(event="assigned")
            task._notify_whatsapp_task(event="assigned")
            task._notify_sms_task(event="assigned")

        if auto_start and user_id:
            task.action_start()

        return task

    def action_start(self):
        for task in self:
            if task.state != "pending":
                raise UserError(
                    _("Only pending housekeeping tasks can be started.")
                )

            if not task.assigned_to:
                raise UserError(
                    _(
                        "Please assign housekeeping task %s "
                        "to a user before starting."
                    )
                    % task.display_name
                )

            task.write({
                "state": "in_progress",
                "started_at": fields.Datetime.now(),
            })

            if task.room_id and task.room_id.status != "cleaning":
                task.room_id.status = "cleaning"

        return True

    def action_done(self):
        self.ensure_one()

        if self.state != "in_progress":
            raise UserError(
                _("Only housekeeping tasks in progress can be completed.")
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Complete Housekeeping"),
            "res_model": "hotel.task.completion.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_task_type": "housekeeping",
                "default_housekeeping_id": self.id,
                "default_completed_at": fields.Datetime.now(),
            },
        }

    def action_cancel(self):
        for task in self:
            if task.state in ("done", "in_progress"):
                raise UserError(
                    _(
                        "Housekeeping tasks that are completed or in progress "
                        "cannot be cancelled."
                    )
                )

            if task.room_id.status in (
                    "reserved",
                    "occupied",
                    "dirty",
                    "maintenance",
            ):
                raise UserError(
                    _(
                        "This housekeeping task cannot be cancelled "
                        "because room %s has status '%s'."
                    ) % (task.room_id.display_name, task.room_id.status)
                )

            task.state = "cancelled"
            task.room_id.write({"status": "dirty"})

            task._notify_assigned_user(event="cancelled")
            task._notify_whatsapp_task(event="cancelled")

        return True

   
    @api.model
    def cron_start_scheduled_tasks(self):
        parameters = self.env["ir.config_parameter"].sudo()

        now = fields.Datetime.now()

        if parameters.get_param(
                "vs_hotel_management.auto_start_housekeeping",
                "False",
        ).lower() in ("true", "1"):
            housekeeping_tasks = self.sudo().search([
                ("state", "=", "pending"),
                ("scheduled_date", "!=", False),
                ("scheduled_date", "<=", now),
            ])

            for task in housekeeping_tasks:
                try:
                    task.action_start()
                except Exception:
                    _logger.exception(
                        "Failed to automatically start housekeeping task %s",
                        task.id,
                    )

        if parameters.get_param(
                "vs_hotel_management.auto_start_maintenance",
                "False",
        ).lower() in ("true", "1"):
            maintenance_tasks = self.env[
                "hotel.maintenance"
            ].sudo().search([
                ("state", "=", "pending"),
                ("scheduled_date", "!=", False),
                ("scheduled_date", "<=", now),
            ])

            for task in maintenance_tasks:
                try:
                    task.action_start()
                except Exception:
                    _logger.exception(
                        "Failed to automatically start maintenance task %s",
                        task.id,
                    )

    def unlink(self):
        for task in self:
            if task.state not in ("pending", "cancelled"):
                raise UserError(
                    _(
                        "Only pending or cancelled housekeeping tasks "
                        "can be deleted. Task %s is currently %s."
                    ) % (task.display_name, task.state)
                )

        return super().unlink()