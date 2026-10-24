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

    scheduled_date = fields.Datetime(
        string="Scheduled Start Date",
        required=True,
        default=fields.Datetime.now,
    )

    assigned_to = fields.Many2one(
        "res.users",
        string="Assign To",
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

    instruction_notes = fields.Text(
        string="Instruction Notes",
    )

    def action_assign(self):
        self.ensure_one()

        if not self.assigned_to:
            raise UserError(_("Please select an employee to assign this task."))

        if not self.room_id:
            raise UserError(_("Please select a room before assigning the task."))

        if self.start_mode == "schedule":

            if not self.scheduled_date:
                raise UserError(
                    _("Please select a scheduled start date and time.")
                )

            if self.scheduled_date < fields.Datetime.now():
                raise UserError(
                    _("The scheduled start time cannot be in the past.")
                )


        room = self.room_id

        if self.task_type == "housekeeping":
            if room.status != "dirty":
                raise UserError(
                    _("Room %s must be Dirty before housekeeping can start.")
                    % room.display_name
                )

            model_name = "hotel.housekeeping"
            task_domain = [
                ("room_id", "=", room.id),
                ("state", "in", ("pending", "in_progress")),
            ]

        elif self.task_type == "maintenance":
            if room.status in (
                    "reserved", "occupied", "cleaning", "maintenance"
            ):
                raise UserError(
                    _("Room %s is currently %s and cannot start maintenance.")
                    % (room.display_name, room.status)
                )

            model_name = "hotel.maintenance"
            task_domain = [
                ("room_id", "=", room.id),
                ("state", "in", ("pending", "in_progress")),
            ]

        else:
            raise UserError(_("Unsupported task type."))

        room._check_active_reservation_booking()

        Task = self.env[model_name]
        task = Task.search(task_domain, order="id desc", limit=1)

        if task and task.state != "pending":
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
            if self.task_type == "housekeeping":
                task = Task.create({
                    "room_id": room.id,
                    "housekeeping_type": self.housekeeping_type,
                    "state": "pending",
                    "scheduled_date": scheduled_date,
                    "assigned_to": self.assigned_to.id,
                    "priority": self.priority,
                    "instruction_notes": self.instruction_notes,
                })
            else:
                task = Task.create({
                    "room_id": room.id,
                    "maintenance_type": self.maintenance_type,
                    "state": "pending",
                    "scheduled_date": scheduled_date,
                    "assigned_to": self.assigned_to.id,
                    "priority": self.priority,
                    "instruction_notes": self.instruction_notes,
                })

        if self.start_mode != "schedule":
            task.action_start()

        if self.task_type == "housekeeping":
            room.status = "cleaning"

        task._notify_assigned_user(event="assigned")
        task._notify_whatsapp_task(event="assigned")

        return {
            "type": "ir.actions.act_window",
            "name": _("Housekeeping") if self.task_type == "housekeeping"
            else _("Maintenance"),
            "res_model": model_name,
            "res_id": task.id,
            "view_mode": "form",
            "target": "current",
        }

class HotelTaskCompletionWizard(models.TransientModel):
    _name = "hotel.task.completion.wizard"
    _description = "Task Completion Wizard"

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

        if task.state != "in_progress":
            raise UserError(
                _("Only tasks in progress can be completed.")
            )

        if not self.completed_at:
            raise UserError(_("Please enter the completion time."))

        if task.started_at and self.completed_at < task.started_at:
            raise UserError(
                _(
                    "The completion time cannot be earlier "
                    "than the start time (%s)."
                ) % task.started_at
            )

        task.write({
            "completed_at": self.completed_at,
            "state": "done",
        })

        if task.room_id.status in ("cleaning", "maintenance"):
            task.room_id.status = "available"

        return {
            "type": "ir.actions.act_window",
            "name": (
                _("Housekeeping")
                if self.task_type == "housekeeping"
                else _("Maintenance")
            ),
            "res_model": (
                "hotel.housekeeping"
                if self.task_type == "housekeeping"
                else "hotel.maintenance"
            ),
            "res_id": task.id,
            "view_mode": "form",
            "target": "current",
        }