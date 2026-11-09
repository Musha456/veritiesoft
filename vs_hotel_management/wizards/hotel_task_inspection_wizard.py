# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HotelTaskInspectionWizard(models.TransientModel):
    """
    Inspection Review Wizard for Housekeeping and Maintenance Tasks.
    Allows managers to approve or reject tasks with required feedback remarks.
    """
    _name = "hotel.task.inspection.wizard"
    _description = "Task Inspection Decision Wizard"

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

    decision = fields.Selection(
        [
            ("passed", "Pass Inspection"),
            ("failed", "Fail Inspection / Request Revision"),
        ],
        string="Inspection Result",
        required=True,
        default="passed",
    )

    inspector_id = fields.Many2one(
        "res.partner",
        string="Inspect Manager",
        required=True,
        default=lambda self: self.env.user.partner_id,
    )

    remarks = fields.Text(
        string="Inspection Remarks / Instructions",
        help="Mandatory if inspection fails. Remarks will be recorded in inspection history and sent to the assigned staff member.",
    )

    def action_confirm(self):
        self.ensure_one()
        task = self.housekeeping_id if self.task_type == "housekeeping" else self.maintenance_id
        if not task:
            raise UserError(_("No task selected for inspection."))

        if self.decision == "failed":
            if not self.remarks or not self.remarks.strip():
                raise UserError(_("Please provide inspection remarks explaining why the task failed and what must be revised."))
            return task.action_reject_inspection(inspector=self.inspector_id, remarks=self.remarks.strip())
        else:
            return task.action_approve_inspection(inspector=self.inspector_id, remarks=self.remarks or "")
