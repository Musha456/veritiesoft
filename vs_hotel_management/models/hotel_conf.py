from odoo import api, fields, models

from odoo import api, fields, models


class HotelService(models.Model):
    _name = "hotel.service"
    _description = "Hotel Service"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, category, name"
    _rec_name = "name"
    _check_company_auto = True

    sequence = fields.Integer(
        default=10,
    )

    active = fields.Boolean(
        default=True,
        tracking=True,
    )

    name = fields.Char(
        required=True,
        translate=True,
        tracking=True,
    )

    code = fields.Char(
        readonly=True,
        copy=False,
        default="/",
        index=True,
        tracking=True,
    )

    image = fields.Image(
        string="Service Image",
        max_width=512,
        max_height=512,
    )

    icon = fields.Char(
        help="Font Awesome icon name (e.g. fa-spa, fa-wifi).",
    )

    hotel_id = fields.Many2one(
        "hotel.hotel",
        required=True,
        ondelete="cascade",
        check_company=True,
        index=True,
    )

    reservation_id = fields.Many2one(
        "hotel.reservation",
        ondelete="cascade",
        index=True,
    )

    reservation_line_id = fields.Many2one(
        "hotel.reservation.line",
        ondelete="cascade",
        index=True,
    )

    category = fields.Selection(
        [
            ("transport", "Transportation"),
            ("food", "Food & Beverage"),
            ("wellness", "Wellness & Spa"),
            ("fitness", "Fitness"),
            ("business", "Business"),
            ("housekeeping", "Housekeeping"),
            ("laundry", "Laundry"),
            ("parking", "Parking"),
            ("recreation", "Recreation"),
            ("general", "General"),
            ("other", "Other"),
        ],
        default="general",
        required=True,
        tracking=True,
    )

    description = fields.Html(
        translate=True,
    )

    is_complimentary = fields.Boolean(
        string="Complimentary",
        default=True,
        tracking=True,
        help="Included in the room rate.",
    )

    price = fields.Monetary(
        tracking=True,
    )

    tax_amount = fields.Monetary(
        tracking=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        related="hotel_id.currency_id",
        store=True,
        readonly=True,
    )

    available_from = fields.Float(
        widget="float_time",
    )

    available_to = fields.Float(
        widget="float_time",
    )

    company_id = fields.Many2one(
        "res.company",
        related="hotel_id.company_id",
        store=True,
        readonly=True,
    )

    @api.depends("price", "is_complimentary")
    def _compute_price(self):
        for rec in self:
            rec.price = 0.0 if rec.is_complimentary else rec.price

    _sql_constraints = [
        (
            "hotel_service_name_unique",
            "unique(hotel_id, name)",
            "The service name must be unique per hotel.",
        ),
        (
            "hotel_service_code_unique",
            "unique(hotel_id, code)",
            "The service code must be unique per hotel.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "/") == "/":
                vals["code"] = self.env["ir.sequence"].next_by_code(
                    "hotel.service"
                ) or "/"
        return super().create(vals_list)