from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HotelTaskAssignmentWizard(models.TransientModel):
    _name = "hotel.task.assignment.wizard"
    _description = "Hotel Task Assignment"

    task_type = fields.Selection(
        [
            ("housekeeping", "Housekeeping"),
            ("maintenance", "Maintenance"),
        ],
        string="Task Type",
        required=True,
        readonly=True,
    )

    room_id = fields.Many2one(
        "hotel.room",
        string="Room",
        required=True,
        readonly=True,
    )

    housekeeping_id = fields.Many2one(
        "hotel.housekeeping",
        string="Housekeeping Task",
        readonly=True,
    )

    maintenance_id = fields.Many2one(
        "hotel.maintenance",
        string="Maintenance Task",
        readonly=True,
    )

    assigned_to = fields.Many2one(
        "res.partner",
        string="Assign Staff",
        required=True,
    )

    start_mode = fields.Selection(
        [
            ("now", "Start Now"),
            ("schedule", "Schedule for Later"),
        ],
        string="Start Mode",
        default="now",
        required=True,
    )

    scheduled_date = fields.Datetime(
        string="Scheduled Start Time",
        default=fields.Datetime.now,
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

    instruction_notes = fields.Text(
        string="Instruction Notes",
    )

    @api.onchange("task_type")
    def _onchange_task_type(self):
        if self.task_type == "housekeeping":
            return {"domain": {"assigned_to": [("is_housekeeping_staff", "=", True)]}}
        elif self.task_type == "maintenance":
            return {"domain": {"assigned_to": [("is_maintenance_staff", "=", True)]}}
        return {"domain": {"assigned_to": []}}

    def action_assign(self):
        self.ensure_one()

        room = self.room_id

        if not room:
            raise UserError(_("Room is required."))

        if not self.assigned_to:
            raise UserError(_("Please select an operational staff member to assign."))

        if self.task_type == "housekeeping":
            model_name = "hotel.housekeeping"
            task_domain = [
                ("room_id", "=", room.id),
                ("state", "in", ("pending", "in_progress", "revision_required")),
            ]
        elif self.task_type == "maintenance":
            model_name = "hotel.maintenance"
            task_domain = [
                ("room_id", "=", room.id),
                ("state", "in", ("pending", "in_progress", "revision_required")),
            ]
        else:
            raise UserError(_("Unsupported task type."))

        room._check_active_reservation_booking()

        Task = self.env[model_name]
        task = Task.search(task_domain, order="id desc", limit=1)

        if task and task.state not in ("pending", "revision_required"):
            raise UserError(
                _("An active task already exists for room %s.")
                % room.display_name
            )

        scheduled_date = (
            self.scheduled_date
            if self.start_mode == "schedule"
            else fields.Datetime.now()
        )

        if not task:
            vals = {
                "room_id": room.id,
                "state": "pending",
                "scheduled_date": scheduled_date,
                "assigned_to": self.assigned_to.id,
                "priority": self.priority,
                "instruction_notes": self.instruction_notes,
                "company_id": room.company_id.id,
            }
            if self.task_type == "housekeeping":
                vals["housekeeping_type"] = self.housekeeping_type
            else:
                vals["maintenance_type"] = self.maintenance_type
            task = Task.create(vals)
        else:
            task.write({
                "assigned_to": self.assigned_to.id,
                "scheduled_date": scheduled_date,
                "instruction_notes": self.instruction_notes or task.instruction_notes,
            })

        if self.start_mode != "schedule":
            task.action_start()

        if self.task_type == "housekeeping":
            if room.status != "cleaning":
                room.write({"status": "cleaning"})
        else:
            if room.status != "maintenance":
                room.write({"status": "maintenance"})

        task._notify_assigned_partner(event="assigned")

        return {
            "type": "ir.actions.act_window",
            "name": _("Housekeeping") if self.task_type == "housekeeping" else _("Maintenance"),
            "res_model": model_name,
            "res_id": task.id,
            "view_mode": "form",
            "target": "current",
        }


class HotelTaskCompletionWizard(models.TransientModel):
    _name = "hotel.task.completion.wizard"
    _description = "Task Completion & Inspection Submission Wizard"

    task_type = fields.Selection(
        [
            ("housekeeping", "Housekeeping"),
            ("maintenance", "Maintenance"),
        ],
        string="Task Type",
        required=True,
        readonly=True,
    )

    housekeeping_id = fields.Many2one(
        "hotel.housekeeping",
        string="Housekeeping Task",
        readonly=True,
    )

    maintenance_id = fields.Many2one(
        "hotel.maintenance",
        string="Maintenance Task",
        readonly=True,
    )

    completed_at = fields.Datetime(
        string="Completion Date",
        required=True,
        default=fields.Datetime.now,
    )

    def action_submit(self):
        self.ensure_one()

        task = (
            self.housekeeping_id
            if self.task_type == "housekeeping"
            else self.maintenance_id
        )

        if not task:
            raise UserError(_("No task was selected for completion."))

        if task.state not in ("in_progress", "revision_required"):
            raise UserError(
                _("Only tasks currently in progress or revision can be submitted for inspection.")
            )

        if not self.completed_at:
            raise UserError(_("Please enter the completion time."))

        if task.started_at and self.completed_at < task.started_at:
            raise UserError(
                _(
                    "The completion time cannot be earlier than the start time (%s)."
                ) % task.started_at
            )

        # Move to Inspection Required workflow (room status remains cleaning/maintenance until approved)
        return task.action_submit_inspection(completed_at=self.completed_at)
