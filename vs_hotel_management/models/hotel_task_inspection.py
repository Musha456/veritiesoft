# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HotelTaskInspection(models.Model):
    """
    Inspection History Log for Housekeeping and Maintenance Tasks.
    Preserves complete audit trail of inspection attempts, results, inspector,
    dates, and required revision remarks.
    """
    _name = "hotel.task.inspection"
    _description = "Hotel Task Inspection History"
    _order = "inspection_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Inspection Reference",
        required=True,
        copy=False,
        readonly=True,
        default="/",
    )

    task_type = fields.Selection(
        [
            ("housekeeping", "Housekeeping"),
            ("maintenance", "Maintenance"),
        ],
        string="Task Type",
        required=True,
        index=True,
    )

    housekeeping_id = fields.Many2one(
        "hotel.housekeeping",
        string="Housekeeping Task",
        ondelete="cascade",
        index=True,
    )

    maintenance_id = fields.Many2one(
        "hotel.maintenance",
        string="Maintenance Task",
        ondelete="cascade",
        index=True,
    )

    room_id = fields.Many2one(
        "hotel.room",
        string="Room",
        required=True,
        index=True,
    )

    hotel_id = fields.Many2one(
        "hotel.hotel",
        string="Hotel",
        related="room_id.hotel_id",
        store=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    assigned_partner_id = fields.Many2one(
        "res.partner",
        string="Assigned Staff",
        index=True,
    )

    inspector_id = fields.Many2one(
        "res.partner",
        string="Inspector",
        required=True,
        index=True,
    )

    inspector_user_id = fields.Many2one(
        "res.users",
        string="Inspector User",
        default=lambda self: self.env.user,
        readonly=True,
    )

    inspection_date = fields.Datetime(
        string="Inspection Date",
        default=fields.Datetime.now,
        required=True,
    )

    result = fields.Selection(
        [
            ("passed", "Passed"),
            ("failed", "Failed / Revision Required"),
        ],
        string="Inspection Result",
        required=True,
        index=True,
    )

    remarks = fields.Text(
        string="Inspection Remarks",
    )

    attempt_number = fields.Integer(
        string="Attempt #",
        default=1,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                prefix = "INSP/HK/" if vals.get("task_type") == "housekeeping" else "INSP/MNT/"
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("hotel.task.inspection")
                    or f"{prefix}{fields.Date.today()}"
                )
        return super().create(vals_list)

    @api.constrains("result", "remarks")
    def _check_failed_remarks(self):
        for record in self:
            if record.result == "failed" and not (record.remarks and record.remarks.strip()):
                raise ValidationError(_("Inspection remarks are mandatory when an inspection fails."))
