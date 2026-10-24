
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HotelWhatsAppTemplate(models.Model):
    _name = "hotel.whatsapp.template"
    _description = "Hotel WhatsApp Message Template"
    _order = "name, language"

    name = fields.Char(
        string="Template Name",
        required=True,
        index=True,
    )
    template_key = fields.Char(
        string="Internal Reference",
        required=True,
        index=True,
        copy=False,
    )
    language = fields.Char(
        string="Language Code",
        required=True,
        default="en",
        help="Must match the language code configured in Meta.",
    )
    category = fields.Selection(
        [
            ("utility", "Utility"),
            ("marketing", "Marketing"),
            ("authentication", "Authentication"),
        ],
        string="Meta Category",
        default="utility",
        required=True,
    )
    task_type = fields.Selection(
        [
            ("housekeeping", "Housekeeping"),
            ("maintenance", "Maintenance"),
            ("reservation", "Reservation"),
            ("both", "All Modules / General"),
        ],
        string="Module / Type",
        default="both",
        required=True,
    )
    event = fields.Selection(
        [
            ("assigned", "Assigned"),
            ("cancelled", "Cancelled"),
            ("confirmed", "Confirmed"),
            ("checkout", "Checked Out"),
            ("both", "All Events / General"),
        ],
        string="Notification Event",
        default="both",
        required=True,
    )
    body_text = fields.Text(
        string="Template Body",
        required=True,
        help="Copy the approved body text from Meta WhatsApp Manager.",
    )
    parameter_count = fields.Integer(
        string="Body Parameters",
        compute="_compute_parameter_count",
        store=True,
    )
    meta_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("paused", "Paused"),
            ("disabled", "Disabled"),
        ],
        string="Meta Approval Status",
        default="draft",
        required=True,
        tracking=True,
    )
    active = fields.Boolean(default=True)
    notes = fields.Text(string="Internal Notes")

    _sql_constraints = [
        (
            "template_key_language_unique",
            "unique(template_key, language)",
            "The internal template reference must be unique per language.",
        ),
    ]

    @api.depends("body_text")
    def _compute_parameter_count(self):
        import re

        for record in self:
            placeholders = re.findall(
                r"\{\{\s*(\d+)\s*\}\}",
                record.body_text or "",
            )
            record.parameter_count = len(set(placeholders))

    @api.constrains("body_text")
    def _check_sequential_parameters(self):
        import re

        for record in self:
            placeholders = re.findall(
                r"\{\{\s*(\d+)\s*\}\}",
                record.body_text or "",
            )
            numbers = sorted({int(value) for value in placeholders})
            if numbers and numbers != list(range(1, max(numbers) + 1)):
                raise ValidationError(
                    _("Template placeholders must be sequential, "
                      "starting at {{1}}.")
                )

    def action_mark_pending(self):
        self.write({"meta_status": "pending"})

    def action_mark_approved(self):
        self.write({"meta_status": "approved"})

    def action_mark_rejected(self):
        self.write({"meta_status": "rejected"})

    def action_mark_paused(self):
        self.write({"meta_status": "paused"})

    def action_mark_draft(self):
        self.write({"meta_status": "draft"})
