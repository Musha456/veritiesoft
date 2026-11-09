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
            ("inspection_required", "Inspection Required"),
            ("revision_required", "Revision Required"),
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
        "res.partner",
        string="Assigned To",
        domain=[("is_housekeeping_staff", "=", True)],
        tracking=True,
    )

    inspector_id = fields.Many2one(
        "res.partner",
        string="Inspector",
        domain=[("is_housekeeping_manager", "=", True)],
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

    duration_seconds = fields.Integer(
        string="Elapsed Time (Seconds)",
        compute="_compute_duration_seconds",
    )

    whatsapp_log_count = fields.Integer(
        string="WhatsApp Logs",
        compute="_compute_whatsapp_log_count",
    )

    inspection_ids = fields.One2many(
        "hotel.task.inspection",
        "housekeeping_id",
        string="Inspection History",
        readonly=True,
    )

    inspection_count = fields.Integer(
        string="Inspections",
        compute="_compute_inspection_count",
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

    @api.depends("inspection_ids")
    def _compute_inspection_count(self):
        for task in self:
            task.inspection_count = len(task.inspection_ids)

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

    def action_view_inspections(self):
        self.ensure_one()
        return {
            "name": _("Inspection History"),
            "type": "ir.actions.act_window",
            "res_model": "hotel.task.inspection",
            "view_mode": "list,form",
            "domain": [("housekeeping_id", "=", self.id)],
            "context": {
                "default_housekeeping_id": self.id,
                "default_task_type": "housekeeping",
                "default_room_id": self.room_id.id,
            },
        }

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
                ("state", "in", ("pending", "in_progress", "inspection_required", "revision_required")),
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

        # assigned_to may be a partner record, partner id, or a user record
        partner_id = False
        if assigned_to:
            if hasattr(assigned_to, '_name'):
                if assigned_to._name == 'res.partner':
                    partner_id = assigned_to.id
                elif assigned_to._name == 'res.users':
                    partner_id = assigned_to.partner_id.id
            else:
                partner_id = int(assigned_to)

        instructions = instruction_notes or _("Checkout room housekeeping cleaning")

        if existing:
            vals = {}
            if partner_id and not existing.assigned_to:
                vals["assigned_to"] = partner_id
            if instructions and not existing.instruction_notes:
                vals["instruction_notes"] = instructions
            if vals:
                existing.write(vals)
            if partner_id:
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
            "assigned_to": partner_id,
            "instruction_notes": instructions,
        })

        if partner_id:
            task._notify_assigned_user(event="assigned")
            task._notify_whatsapp_task(event="assigned")
            task._notify_sms_task(event="assigned")

        if auto_start and partner_id:
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
                        "to a staff member before starting."
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

        if self.state not in ("in_progress", "revision_required"):
            raise UserError(
                _("Only housekeeping tasks in progress or revision required can be completed.")
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

    def action_submit_inspection(self, completed_at=None):
        """Called by the completion wizard to move task to inspection_required."""
        self.ensure_one()
        if self.state not in ("in_progress", "revision_required"):
            raise UserError(
                _("Only tasks in progress or revision required can be submitted for inspection.")
            )

        vals = {
            "state": "inspection_required",
        }
        if completed_at:
            vals["completed_at"] = completed_at

        self.write(vals)

        # Notify inspector if set
        if self.inspector_id:
            self._notify_inspection_required(self.inspector_id)

        return {
            "type": "ir.actions.act_window",
            "name": _("Housekeeping"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_approve_inspection(self, inspector=None, remarks=""):
        """Manager approves inspection — task moves to Done, room to available."""
        self.ensure_one()
        if self.state != "inspection_required":
            raise UserError(
                _("Only tasks in 'Inspection Required' state can be approved.")
            )

        inspector_partner = inspector or self.inspector_id or self.env.user.partner_id
        attempt = len(self.inspection_ids) + 1

        self.env["hotel.task.inspection"].create({
            "task_type": "housekeeping",
            "housekeeping_id": self.id,
            "room_id": self.room_id.id,
            "company_id": self.company_id.id,
            "assigned_partner_id": self.assigned_to.id if self.assigned_to else False,
            "inspector_id": inspector_partner.id,
            "inspector_user_id": self.env.user.id,
            "result": "passed",
            "remarks": remarks or "",
            "attempt_number": attempt,
        })

        self.write({
            "state": "done",
            "inspector_id": inspector_partner.id,
        })

        # Mark room as available if no active maintenance
        if self.room_id:
            active_maintenance = self.env["hotel.maintenance"].search([
                ("room_id", "=", self.room_id.id),
                ("state", "in", ("pending", "in_progress", "inspection_required", "revision_required")),
            ], limit=1)
            if not active_maintenance:
                self.room_id.write({"status": "available"})

        self._notify_inspection_passed()

        return {
            "type": "ir.actions.act_window",
            "name": _("Housekeeping"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_reject_inspection(self, inspector=None, remarks=""):
        """Manager rejects inspection — task goes back to Revision Required."""
        self.ensure_one()
        if self.state != "inspection_required":
            raise UserError(
                _("Only tasks in 'Inspection Required' state can be rejected.")
            )
        if not remarks or not remarks.strip():
            raise UserError(
                _("Inspection remarks are mandatory when rejecting / requesting revision.")
            )

        inspector_partner = inspector or self.inspector_id or self.env.user.partner_id
        attempt = len(self.inspection_ids) + 1

        self.env["hotel.task.inspection"].create({
            "task_type": "housekeeping",
            "housekeeping_id": self.id,
            "room_id": self.room_id.id,
            "company_id": self.company_id.id,
            "assigned_partner_id": self.assigned_to.id if self.assigned_to else False,
            "inspector_id": inspector_partner.id,
            "inspector_user_id": self.env.user.id,
            "result": "failed",
            "remarks": remarks.strip(),
            "attempt_number": attempt,
        })

        self.write({
            "state": "revision_required",
            "inspector_id": inspector_partner.id,
        })

        self._notify_inspection_failed(remarks.strip())

        return {
            "type": "ir.actions.act_window",
            "name": _("Housekeeping"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_resubmit(self):
        """Staff resubmits task for inspection after revision."""
        self.ensure_one()
        if self.state != "revision_required":
            raise UserError(
                _("Only tasks in 'Revision Required' state can be resubmitted.")
            )

        self.write({"state": "inspection_required"})

        if self.inspector_id:
            self._notify_inspection_required(self.inspector_id)

        return True

    def action_open_inspection_wizard(self):
        """Open the inspection decision wizard (for managers)."""
        self.ensure_one()
        if self.state != "inspection_required":
            raise UserError(_("This task is not pending inspection."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Inspect Housekeeping Task"),
            "res_model": "hotel.task.inspection.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_task_type": "housekeeping",
                "default_housekeeping_id": self.id,
                "default_inspector_id": self.inspector_id.id if self.inspector_id else self.env.user.partner_id.id,
            },
        }

    def action_cancel(self):
        for task in self:
            if task.state in ("done", "in_progress", "inspection_required"):
                raise UserError(
                    _(
                        "Housekeeping tasks that are completed, in progress, or pending inspection "
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
