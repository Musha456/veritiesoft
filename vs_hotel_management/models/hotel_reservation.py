from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo import Command


class HotelReservation(models.Model):
    _name = "hotel.reservation"
    _description = "Hotel Reservation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "check_in desc, id desc"
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

    name = fields.Char(
        string="Reservation",
        default="/",
        copy=False,
        readonly=True,
        tracking=True,
        index=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("reserved", "Reserved"),
            ("checked_in", "Checked In"),
            ("checked_out", "Checked Out"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
            ("no_show", "No Show"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        copy=False,
        index=True,
    )

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    # ---------------------------------------------------------
    # Hotel
    # ---------------------------------------------------------

    hotel_id = fields.Many2one(
        "hotel.hotel",
        required=True,
        tracking=True,
        check_company=True,
    )

    # ---------------------------------------------------------
    # Guest
    # ---------------------------------------------------------

    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        tracking=True,
    )

    # ---------------------------------------------------------
    # Stay
    # ---------------------------------------------------------

    check_in = fields.Datetime(
        required=True,
        tracking=True,
    )

    check_out = fields.Datetime(
        required=True,
        tracking=True,
    )

    night_count = fields.Integer(
        compute="_compute_nights",
        store=True,
    )

    guest_count = fields.Integer(
        string="Guests",
        compute="_compute_statistics",
    )

    # ---------------------------------------------------------
    # Pricing
    # ---------------------------------------------------------

    currency_id = fields.Many2one(
        related="hotel_id.currency_id",
        store=True,
        readonly=True,
    )

    discount_amount = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    tax_amount = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    subtotal = fields.Monetary(
        string="Subtotal",
        compute="_compute_amounts",
        currency_field="currency_id",
    )

    room_amount = fields.Monetary(
        string="Room Amount",
        compute="_compute_amounts",
        currency_field="currency_id",
    )

    service_amount = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    total_amount = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    booking_date = fields.Datetime(
        string="Booking Date",
        default=fields.Datetime.now,
        readonly=True,
        tracking=True,
    )

    reservation_type = fields.Selection(
        [
            ("individual", "Individual"),
            ("corporate", "Corporate"),
            ("group", "Group"),
        ],
        string="Reservation Type",
        default="individual",
        tracking=True,
    )

    booking_source = fields.Selection(
        [
            ("walk_in", "Walk-in"),
            ("phone", "Phone"),
            ("email", "Email"),
            ("website", "Website"),
            ("booking", "Booking.com"),
            ("airbnb", "Airbnb"),
            ("expedia", "Expedia"),
            ("travel_agent", "Travel Agent"),
            ("other", "Other"),
        ],
        string="Booking Source",
        default="walk_in",
        tracking=True,
    )

    reference = fields.Char(
        string="Reference",
        tracking=True,
        help="External booking reference or OTA reservation number.",
    )

    arrival_time = fields.Float(
        string="Expected Arrival",
        help="Expected arrival time (24-hour format).",
    )

    departure_time = fields.Float(
        string="Expected Departure",
        help="Expected departure time (24-hour format).",
    )

    payment_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("partial", "Partially Paid"),
            ("paid", "Paid"),
            ("refunded", "Refunded"),
        ],
        string="Payment Status",
        default="pending",
        tracking=True,
    )

    payment_method = fields.Selection(
        [
            ("cash", "Cash"),
            ("card", "Credit/Debit Card"),
            ("bank", "Bank Transfer"),
            ("online", "Online Payment"),
            ("mixed", "Multiple Methods"),
        ],
        string="Preferred Payment Method",
    )

    untaxed_amount = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    line_ids = fields.One2many(
        "hotel.reservation.line",
        "reservation_id",
        string="Rooms",
    )

    service_ids = fields.One2many(
        "hotel.service",
        "reservation_id",
        string="Services",
    )

    # payment_ids = fields.One2many(
    #     "hotel.reservation.payment",
    #     "reservation_id",
    #     string="Payments",
    # )



    # ---------------------------------------------------------
    # Statistics
    # ---------------------------------------------------------
    room_count = fields.Integer(
        compute="_compute_statistics",
    )

    service_count = fields.Integer(
        compute="_compute_statistics",
    )

    payment_count = fields.Integer(
        compute="_compute_statistics",
    )

    invoice_count = fields.Integer(
        compute="_compute_statistics",
    )

    special_request = fields.Html(
        string="Special Requests",
        translate=True,
    )

    internal_note = fields.Text(
        string="Internal Notes",
    )

    # ---------------------------------------------------------
    # Compute
    # ---------------------------------------------------------

    @api.depends("check_in", "check_out")
    def _compute_nights(self):
        for record in self:
            record.night_count = 0

            if record.check_in and record.check_out:
                delta = record.check_out.date() - record.check_in.date()
                record.night_count = max(delta.days, 1)

    @api.depends(
        "line_ids",
        "line_ids.room_amount",
        "line_ids.service_amount",
        "line_ids.discount_amount",
        "line_ids.tax_amount",
        "line_ids.subtotal",
        "line_ids.total",
    )
    def _compute_amounts(self):

        for reservation in self:
            lines = reservation.line_ids

            reservation.room_amount = sum(
                lines.mapped("room_amount")
            )

            reservation.service_amount = sum(
                lines.mapped("service_amount")
            )

            reservation.discount_amount = sum(
                lines.mapped("discount_amount")
            )

            reservation.tax_amount = sum(
                lines.mapped("tax_amount")
            )

            reservation.subtotal = sum(
                lines.mapped("subtotal")
            )

            reservation.total_amount = sum(
                lines.mapped("total")
            )

    @api.depends(
        "line_ids",
        "line_ids.night_count",
        "line_ids.adults",
        "line_ids.children",
        "line_ids.infants",
    )
    def _compute_statistics(self):

        for reservation in self:
            reservation.room_count = len(
                reservation.line_ids
            )

            reservation.night_count = sum(
                reservation.line_ids.mapped("night_count")
            )

            reservation.guest_count = sum(
                reservation.line_ids.mapped("guest_count")
            )

    # ---------------------------------------------------------
    # Constraints
    # ---------------------------------------------------------

    @api.constrains("check_in", "check_out")
    def _check_dates(self):
        for record in self:
            if record.check_in >= record.check_out:
                raise ValidationError(
                    _("Check-out must be after check-in.")
                )

    @api.constrains("adults")
    def _check_adults(self):
        for record in self:
            if record.adults <= 0:
                raise ValidationError(
                    _("At least one adult is required.")
                )

    # ---------------------------------------------------------
    # ORM
    # ---------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "hotel.reservation"
                ) or "/"

        return super().create(vals_list)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for reservation in records:
            if reservation.state != "draft":
                reservation._validate_reservation()

        return records

    def write(self, vals):

        if "line_ids" in vals:

            if self._has_line_modification(vals["line_ids"]):

                if any(
                        record.state
                        not in ("draft", "cancelled", "no_show")
                        for record in self
                ):
                    raise UserError(
                        _(
                            "Reservation lines cannot be modified "
                            "after the reservation becomes operational."
                        )
                    )

        protected_fields = {
            "hotel_id",
            "check_in",
            "check_out",
            "partner_id",
        }

        if (
                protected_fields.intersection(vals)
                and any(
            record.state not in ("draft", "cancelled", "no_show")
            for record in self
        )
        ):
            raise UserError(
                _(
                    "Operational reservations cannot be modified directly."
                )
            )

        return super().write(vals)

    def unlink(self):

        for reservation in self:

            if reservation.state != "draft":
                raise UserError(
                    _(
                        "Only draft reservations can be deleted."
                    )
                )

        return super().unlink()

    def _has_line_modification(self, commands):

        for command in commands:

            if not command:
                continue

            operation = command[0]

            if operation in (
                    Command.CREATE,
                    Command.UPDATE,
                    Command.DELETE,
                    Command.UNLINK,
                    Command.CLEAR,
                    Command.SET,
            ):
                return True

        return False

    # ---------------------------------------------------------
    # Actions
    # ---------------------------------------------------------

    def action_confirm(self):

        for reservation in self:

            if reservation.state != "draft":
                raise UserError(
                    _(
                        "Only draft reservations can be confirmed."
                    )
                )

            reservation._validate_reservation()

            reservation.state = "confirmed"

    def action_reserve(self):

        for reservation in self:

            if reservation.state != "confirmed":
                raise UserError(
                    _(
                        "Only confirmed reservations can be reserved."
                    )
                )

            reservation._validate_reservation()

            for line in reservation.line_ids:
                line._assign_room()

            reservation.state = "reserved"

    def action_check_in(self):

        for reservation in self:

            if reservation.state != "reserved":
                continue

            for line in reservation.line_ids:
                line._update_room_status("occupied")

            reservation.state = "checked_in"

    def action_check_out(self):

        for reservation in self:

            if reservation.state != "checked_in":
                continue

            for line in reservation.line_ids:
                line._update_room_status("cleaning")

            reservation.state = "checked_out"

    def action_complete(self):

        for reservation in self:

            if reservation.state != "checked_out":
                continue

            for line in reservation.line_ids:
                line._release_room()

            reservation.state = "completed"

    def action_cancel(self):

        for reservation in self:

            if reservation.state in (
                    "checked_out",
                    "completed",
            ):
                raise UserError(
                    _(
                        "A checked-out or completed reservation "
                        "cannot be cancelled."
                    )
                )

            for line in reservation.line_ids:
                line._release_room()

            reservation.state = "cancelled"

    def action_no_show(self):

        for reservation in self:

            if reservation.state != "reserved":
                continue

            for line in reservation.line_ids:
                line._release_room()

            reservation.state = "no_show"

    def action_reset_to_draft(self):

        for reservation in self:

            if reservation.state not in (
                    "confirmed",
                    "cancelled",
                    "no_show",
            ):
                raise UserError(
                    _(
                        "Only confirmed, cancelled, or no-show "
                        "reservations can be reset to draft."
                    )
                )

            reservation.state = "draft"

    def _validate_reservation(self):

        self.ensure_one()

        if not self.line_ids:
            raise ValidationError(
                _("Please add at least one reservation line.")
            )

        self._check_duplicate_rooms()

        for line in self.line_ids:
            line._validate_booking_period()
            line._validate_capacity()
            line._validate_room()
            line._validate_rate_plan()
            line._validate_discount()

            if not line._is_room_available():
                raise ValidationError(
                    _(
                        "Room '%s' is not available "
                        "for the selected dates."
                    ) % line.room_id.display_name
                )

    def _check_duplicate_rooms(self):

        self.ensure_one()

        rooms = self.line_ids.mapped("room_id")

        for room in rooms:

            lines = self.line_ids.filtered(
                lambda line: line.room_id == room
            )

            if len(lines) <= 1:
                continue

            for index, line in enumerate(lines):

                for other in lines[index + 1:]:

                    if (
                            line.check_in < other.check_out
                            and line.check_out > other.check_in
                    ):
                        raise ValidationError(
                            _(
                                "Room '%s' is assigned more than once "
                                "for overlapping dates."
                            ) % room.display_name
                        )

