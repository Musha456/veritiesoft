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
        "res.users",
        string="Assign To",
        required=True,
    )

    @api.onchange("task_type")
    def _onchange_task_type(self):
        self.assigned_to = False

    def action_assign(self):
        self.ensure_one()

        if not self.assigned_to:
            raise UserError(
                _("Please select an employee to assign this task.")
            )

        if self.task_type == "housekeeping":
            task = self.housekeeping_id

            if not task:
                raise UserError(
                    _("No housekeeping task was found.")
                )

            if task.state not in ("pending", "in_progress"):
                raise UserError(
                    _("This housekeeping task cannot be assigned.")
                )

            task.write({
                "assigned_to": self.assigned_to.id,
            })

            if self.room_id.status == "dirty":
                self.room_id.status = "cleaning"

            if task.state == "pending":
                task.action_start()

        elif self.task_type == "maintenance":

            task = self.maintenance_id

            if not task:
                raise UserError(

                    _("No maintenance request was found.")

                )

            if task.state not in ("pending", "in_progress"):
                raise UserError(

                    _("This maintenance request cannot be assigned.")

                )

            task.write({

                "assigned_to": self.assigned_to.id,

            })

            if self.room_id.status != "maintenance":
                self.room_id.status = "maintenance"

            if task.state == "pending":
                task.action_start()

    @api.onchange("task_type")
    def _onchange_task_type(self):
        self.assigned_to = False

        if self.task_type == "housekeeping":
            return {
                "domain": {
                    "assigned_to": [
                        ("active", "=", True),
                        (
                            "groups_id",
                            "in",
                            [
                                self.env.ref(
                                    "vs_hotel_management.group_hotel_housekeeping_user"
                                ).id
                            ],
                        ),
                    ]
                }
            }

        if self.task_type == "maintenance":
            return {
                "domain": {
                    "assigned_to": [
                        ("active", "=", True),
                        (
                            "groups_id",
                            "in",
                            [
                                self.env.ref(
                                    "vs_hotel_management.group_hotel_maintenance_user"
                                ).id
                            ],
                        ),
                    ]
                }
            }

