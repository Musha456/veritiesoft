from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


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

    reservation_id = fields.Many2one(
        "hotel.reservation",
        string="Reservation",
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
            ("inspection_required", "Inspection Required"),
            ("revision_required", "Revision Required"),
            ("done", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="pending",
        required=True,
        tracking=True,
        copy=False,
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
        "res.partner",
        string="Assigned To",
        domain=[("is_maintenance_staff", "=", True)],
        tracking=True,
    )

    inspector_id = fields.Many2one(
        "res.partner",
        string="Inspector",
        domain=[("is_maintenance_manager", "=", True)],
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
        "maintenance_id",
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
                "default_task_type": "maintenance",
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
            "domain": [("maintenance_id", "=", self.id)],
            "context": {
                "default_maintenance_id": self.id,
                "default_task_type": "maintenance",
                "default_room_id": self.room_id.id,
            },
        }

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
                        "to a staff member before starting."
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

        if self.state not in ("in_progress", "revision_required"):
            raise UserError(
                _("Only maintenance tasks in progress or revision required can be completed.")
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

        if self.inspector_id:
            self._notify_inspection_required(self.inspector_id)

        return {
            "type": "ir.actions.act_window",
            "name": _("Maintenance"),
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
            "task_type": "maintenance",
            "maintenance_id": self.id,
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

        # Mark room as available if no active housekeeping
        if self.room_id:
            active_hk = self.env["hotel.housekeeping"].search([
                ("room_id", "=", self.room_id.id),
                ("state", "in", ("pending", "in_progress", "inspection_required", "revision_required")),
            ], limit=1)
            if not active_hk:
                self.room_id.write({"status": "available"})

        self._notify_inspection_passed()

        return {
            "type": "ir.actions.act_window",
            "name": _("Maintenance"),
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
            "task_type": "maintenance",
            "maintenance_id": self.id,
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
            "name": _("Maintenance"),
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
            "name": _("Inspect Maintenance Task"),
            "res_model": "hotel.task.inspection.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_task_type": "maintenance",
                "default_maintenance_id": self.id,
                "default_inspector_id": self.inspector_id.id if self.inspector_id else self.env.user.partner_id.id,
            },
        }

    def action_cancel(self):
        for task in self:
            if task.state in ("done", "in_progress", "inspection_required"):
                raise UserError(
                    _(
                        "Maintenance tasks that are completed, in progress, or pending inspection "
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
            task._notify_whatsapp_task(event="cancelled")

        return True

    def _find_active_maintenance(self, room):
        return self.search(
            [
                ("room_id", "=", room.id),
                ("state", "in", ("pending", "in_progress", "inspection_required", "revision_required")),
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
