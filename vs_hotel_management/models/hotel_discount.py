from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HotelDiscount(models.Model):
    _name = "hotel.discount"
    _description = "Hotel Discount"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _rec_name = "name"
    _check_company_auto = True

    # ---------------------------------------------------------
    # General Information
    # ---------------------------------------------------------

    sequence = fields.Integer(
        default=10,
    )

    active = fields.Boolean(
        default=True,
        tracking=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("expired", "Expired"),
        ],
        default="draft",
        tracking=True,
        copy=False,
        index=True,
    )

    name = fields.Char(
        required=True,
        tracking=True,
        translate=True,
    )

    code = fields.Char(
        default="/",
        readonly=True,
        copy=False,
        tracking=True,
        index=True,
    )

    description = fields.Html(
        translate=True,
    )

    internal_note = fields.Text(
        tracking=True,
    )

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    hotel_id = fields.Many2one(
        "hotel.hotel",
        required=True,
        ondelete="cascade",
        check_company=True,
        tracking=True,
    )

    currency_id = fields.Many2one(
        related="hotel_id.currency_id",
        store=True,
        readonly=True,
    )

    # ---------------------------------------------------------
    # Discount Configuration
    # ---------------------------------------------------------

    discount_type = fields.Selection(
        [
            ("percentage", "Percentage"),
            ("fixed", "Fixed Amount"),
        ],
        required=True,
        default="percentage",
        tracking=True,
    )

    discount = fields.Float(
        required=True,
        tracking=True,
        help="Percentage or fixed amount depending on the discount type.",
    )

    maximum_discount = fields.Monetary(
        currency_field="currency_id",
        help="Maximum discount amount when using percentage discounts.",
    )

    priority = fields.Selection(
        [
            ("0", "Low"),
            ("1", "Normal"),
            ("2", "High"),
            ("3", "Very High"),
        ],
        default="1",
        tracking=True,
    )

    is_default = fields.Boolean(
        tracking=True,
    )

    website_published = fields.Boolean(
        default=True,
        tracking=True,
    )

    combinable = fields.Boolean(
        string="Can be Combined",
        default=False,
        tracking=True,
    )

    # ---------------------------------------------------------
    # Applicability
    # ---------------------------------------------------------

    rate_plan_ids = fields.Many2many(
        "hotel.rate.plan",
        string="Rate Plans",
    )

    room_category_ids = fields.Many2many(
        "hotel.room.category",
        string="Room Categories",
    )

    # ---------------------------------------------------------
    # Validity
    # ---------------------------------------------------------

    date_start = fields.Date(
        tracking=True,
    )

    date_end = fields.Date(
        tracking=True,
    )

    # ---------------------------------------------------------
    # Booking Rules
    # ---------------------------------------------------------

    minimum_nights = fields.Integer(
        default=1,
    )

    maximum_nights = fields.Integer(
        default=0,
        help="0 means no limit.",
    )

    minimum_amount = fields.Monetary(
        currency_field="currency_id",
    )

    minimum_adults = fields.Integer(
        default=1,
    )

    minimum_children = fields.Integer(
        default=0,
    )

    minimum_advance_days = fields.Integer(
        default=0,
    )

    maximum_advance_days = fields.Integer(
        default=365,
    )

    coupon_required = fields.Boolean()

    coupon_code = fields.Char()

    # ---------------------------------------------------------
    # Availability
    # ---------------------------------------------------------

    monday = fields.Boolean(default=True)

    tuesday = fields.Boolean(default=True)

    wednesday = fields.Boolean(default=True)

    thursday = fields.Boolean(default=True)

    friday = fields.Boolean(default=True)

    saturday = fields.Boolean(default=True)

    sunday = fields.Boolean(default=True)

    # ---------------------------------------------------------
    # Statistics
    # ---------------------------------------------------------

    reservation_count = fields.Integer(
        compute="_compute_statistics",
    )

    discount_amount = fields.Monetary(
        compute="_compute_statistics",
        currency_field="currency_id",
    )

    # ---------------------------------------------------------
    # Compute
    # ---------------------------------------------------------

    @api.depends()
    def _compute_statistics(self):
        for record in self:
            record.reservation_count = 0
            record.discount_amount = 0.0

    # ---------------------------------------------------------
    # Constraints
    # ---------------------------------------------------------

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for record in self:
            if (
                record.date_start
                and record.date_end
                and record.date_start > record.date_end
            ):
                raise ValidationError(
                    _("The end date must be greater than or equal to the start date.")
                )

    @api.constrains("discount")
    def _check_discount(self):
        for record in self:
            if record.discount <= 0:
                raise ValidationError(
                    _("Discount must be greater than zero.")
                )

            if (
                record.discount_type == "percentage"
                and record.discount > 100
            ):
                raise ValidationError(
                    _("Percentage discount cannot exceed 100%.")
                )

    @api.constrains("minimum_nights", "maximum_nights")
    def _check_nights(self):
        for record in self:
            if (
                record.maximum_nights
                and record.minimum_nights > record.maximum_nights
            ):
                raise ValidationError(
                    _("Minimum nights cannot exceed maximum nights.")
                )

    @api.constrains("is_default", "hotel_id")
    def _check_default_discount(self):
        for record in self.filtered("is_default"):
            duplicate = self.search(
                [
                    ("hotel_id", "=", record.hotel_id.id),
                    ("is_default", "=", True),
                    ("id", "!=", record.id),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _("Only one default discount is allowed per hotel.")
                )

    # ---------------------------------------------------------
    # ORM
    # ---------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "/") == "/":
                vals["code"] = self.env["ir.sequence"].next_by_code(
                    "hotel.discount"
                ) or "/"

        return super().create(vals_list)

    # ---------------------------------------------------------
    # Actions
    # ---------------------------------------------------------

    def action_activate(self):
        self.write({
            "state": "active",
            "active": True,
        })

    def action_expire(self):
        self.write({
            "state": "expired",
        })

    def action_reset_to_draft(self):
        self.write({
            "state": "draft",
            "active": True,
        })

    # ---------------------------------------------------------
    # SQL Constraints
    # ---------------------------------------------------------

    _sql_constraints = [
        (
            "hotel_discount_name_unique",
            "unique(name, hotel_id)",
            "Discount name must be unique per hotel.",
        ),
        (
            "hotel_discount_code_unique",
            "unique(code, company_id)",
            "Discount code must be unique.",
        ),
    ]