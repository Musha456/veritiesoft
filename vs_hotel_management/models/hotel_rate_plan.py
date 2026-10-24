from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from pkg_resources import require


class HotelRatePlan(models.Model):
    _name = "hotel.rate.plan"
    _description = "Hotel Rate Plan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
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
        tracking=True,
        translate=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("expired", "Expired"),
            ("archived", "Archived"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        copy=False,
        index=True,
    )

    code = fields.Char(
        readonly=True,
        copy=False,
        default="/",
        tracking=True,
        index=True,
    )

    description = fields.Html(
        translate=True,
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
        "res.currency",
        related="hotel_id.currency_id",
        store=True,
        readonly=True,
    )

    room_category_ids = fields.Many2many(
        "hotel.room.category",
        required=True,
        string="Room Categories",
    )

    base_price = fields.Monetary(
        string="Base Price",
        required=True,
        currency_field="currency_id",
        tracking=True,
    )

    extra_adult_price = fields.Monetary(
        string="Extra Adult Price",
        currency_field="currency_id",
    )

    child_price = fields.Monetary(
        string="Child Price",
        currency_field="currency_id",
    )

    meal_plan = fields.Selection(
        [
            ("room_only", "Room Only"),
            ("breakfast", "Breakfast Included"),
            ("half_board", "Half Board"),
            ("full_board", "Full Board"),
            ("all_inclusive", "All Inclusive"),
        ],
        string="Meal Plan",
        default="room_only",
        tracking=True,
    )

    cancellation_policy = fields.Selection(
        [
            ("flexible", "Flexible"),
            ("moderate", "Moderate"),
            ("strict", "Strict"),
            ("non_refundable", "Non-refundable"),
        ],
        string="Cancellation Policy",
        default="flexible",
        tracking=True,
    )

    date_start = fields.Date(
        string="Valid From",
        tracking=True,
    )

    date_end = fields.Date(
        string="Valid Until",
        tracking=True,
    )

    pricing_method = fields.Selection(
        [
            ("per_room", "Per Room"),
            ("per_guest", "Per Guest"),
            ("per_person", "Per Person"),
        ],
        default="per_room",
        required=True,
        tracking=True,
    )

    rate_type = fields.Selection(
        [
            ("standard", "Standard"),
            ("corporate", "Corporate"),
            ("promotion", "Promotion"),
            ("member", "Member"),
            ("government", "Government"),
            ("package", "Package"),
        ],
        default="standard",
        tracking=True,
    )

    priority = fields.Selection(
        [
            ("0", "Low"),
            ("1", "Normal"),
            ("2", "High"),
            ("3", "Very High"),
        ],
        default="1",
    )

    is_default = fields.Boolean(
        string="Default Rate Plan",
        tracking=True,
    )

    website_published = fields.Boolean(
        default=True,
        tracking=True,
    )



    minimum_nights = fields.Integer(
        string="Minimum Nights",
        default=1,
    )

    maximum_nights = fields.Integer(
        string="Maximum Nights",
        default=30,
    )

    minimum_adults = fields.Integer(
        string="Minimum Adults",
        default=1,
    )

    maximum_adults = fields.Integer(
        string="Maximum Adults",
        default=2,
    )

    minimum_children = fields.Integer(
        string="Minimum Children",
        default=0,
    )

    maximum_children = fields.Integer(
        string="Maximum Children",
        default=2,
    )

    minimum_advance_days = fields.Integer(
        string="Minimum Advance Booking (Days)",
        default=0,
    )

    maximum_advance_days = fields.Integer(
        string="Maximum Advance Booking (Days)",
        default=365,
    )

    monday = fields.Boolean(default=True)

    tuesday = fields.Boolean(default=True)

    wednesday = fields.Boolean(default=True)

    thursday = fields.Boolean(default=True)

    friday = fields.Boolean(default=True)

    saturday = fields.Boolean(default=True)

    sunday = fields.Boolean(default=True)

    reservation_count = fields.Integer(
        string="Reservations",
        compute="_compute_statistics",
    )

    average_booking_value = fields.Monetary(
        compute="_compute_statistics",
        currency_field="currency_id",
    )

    active_reservation_count = fields.Integer(
        compute="_compute_statistics",
    )

    internal_note = fields.Text(
        tracking=True,
    )

    revenue = fields.Monetary(
        string="Revenue",
        compute="_compute_statistics",
        currency_field="currency_id",
    )

    @api.depends()
    def _compute_statistics(self):
        for record in self:
            record.average_booking_value = 0
            record.active_reservation_count = 0
            record.reservation_count = 0
            record.revenue = 0.0

    @api.constrains("date_start", "date_end")
    def _check_validity_dates(self):
        for record in self:
            if (
                    record.date_start
                    and record.date_end
                    and record.date_start > record.date_end
            ):
                raise ValidationError(
                    _("The end date must be greater than or equal to the start date.")
                )

    @api.constrains("is_default", "hotel_id")
    def _check_default_rate_plan(self):
        for record in self.filtered("is_default"):
            duplicate = self.search([
                ("hotel_id", "=", record.hotel_id.id),
                ("is_default", "=", True),
                ("id", "!=", record.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    _("Only one default rate plan is allowed per hotel.")
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

    @api.constrains("minimum_adults", "maximum_adults")
    def _check_adults(self):
        for record in self:
            if (
                    record.maximum_adults
                    and record.minimum_adults > record.maximum_adults
            ):
                raise ValidationError(
                    _("Minimum adults cannot exceed maximum adults.")
                )

    @api.constrains("minimum_children", "maximum_children")
    def _check_children(self):
        for record in self:
            if (
                    record.maximum_children
                    and record.minimum_children > record.maximum_children
            ):
                raise ValidationError(
                    _("Minimum children cannot exceed maximum children.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "/") == "/":
                vals["code"] = self.env["ir.sequence"].next_by_code(
                    "hotel.rate.plan"
                ) or "/"

        return super().create(vals_list)

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

    def action_archive(self):
        self.write({
            "state": "archived",
            "active": False,
        })

    def action_unarchive(self):
        self.write({
            "state": "draft",
            "active": True,
        })

    @api.depends("date_end")
    def _compute_state(self):
        today = fields.Date.context_today(self)

        for record in self:
            if (
                    record.state == "active"
                    and record.date_end
                    and record.date_end < today
            ):
                record.state = "expired"

    _sql_constraints = [
        (
            "hotel_rate_plan_name_unique",
            "unique(name, hotel_id)",
            "Rate plan name must be unique per hotel.",
        ),
        (
            "hotel_rate_plan_code_unique",
            "unique(code, company_id)",
            "Rate plan code must be unique.",
        ),
    ]
