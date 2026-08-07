from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HotelReservationLine(models.Model):
    _name = "hotel.reservation.line"
    _description = "Hotel Reservation Line"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence desc, id desc"
    _check_company_auto = True

    sequence = fields.Integer(
        default=10,
    )

    active = fields.Boolean(
        default=True,
    )

    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    reservation_id = fields.Many2one(
        "hotel.reservation",
        required=True,
        ondelete="cascade",
        index=True,
    )

    hotel_id = fields.Many2one(
        related="reservation_id.hotel_id",
        store=True,
        readonly=True,
    )

    building_id = fields.Many2one(
        "hotel.building",
        required=True,
        domain="[('hotel_id','=',hotel_id)]",
    )

    floor_id = fields.Many2one(
        "hotel.building.floor",
        required=True,
        domain="[('building_id','=',building_id)]",
    )

    room_category_id = fields.Many2one(
        "hotel.room.category",
        required=True,
    )

    room_id = fields.Many2one(
        "hotel.room",
        required=True,
        domain="""
        [
            ('building_id','=',building_id),
            ('floor_id','=',floor_id),
            ('room_category_id','=',room_category_id),
            ('status','=','available')
        ]
        """,
    )

    adults = fields.Integer(
        default=1,
    )

    children = fields.Integer(
        default=0,
    )

    infants = fields.Integer(
        default=0,
    )

    guest_count = fields.Integer(
        compute="_compute_guest_count",
        store=True,
    )

    # check_in = fields.Datetime(
    #     related="reservation_id.check_in",
    #     store=True,
    #     readonly=False,
    # )
    #
    # check_out = fields.Datetime(
    #     related="reservation_id.check_out",
    #     store=True,
    #     readonly=False,
    # )

    night_count = fields.Integer(
        compute="_compute_nights",
        store=True,
    )

    currency_id = fields.Many2one(
        related="hotel_id.currency_id",
        store=True,
        readonly=True,
    )

    room_name = fields.Char(
        related="room_id.display_name",
        store=True,
    )

    room_code = fields.Char(
        related="room_id.code",
        store=True,
    )

    bed_type_id = fields.Many2one(
        related="room_category_id.bed_type_id",
        store=True,
    )

    bed_count = fields.Integer(
        related="room_category_id.bed_count",
        store=True,
    )

    room_size = fields.Float(
        related="room_category_id.room_size",
        store=True,
    )

    meal_plan = fields.Selection(
        related="rate_plan_id.meal_plan",
        store=True,
    )

    cancellation_policy = fields.Selection(
        related="rate_plan_id.cancellation_policy",
        store=True,
    )

    rate_plan_id = fields.Many2one(
        "hotel.rate.plan",
        required=True,
    )

    discount_id = fields.Many2one(
        "hotel.discount",
    )

    base_price = fields.Monetary(
        currency_field="currency_id",
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
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    total = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    service_ids = fields.One2many(
        "hotel.service",
        "reservation_line_id",
        string="Services",
    )

    service_amount = fields.Monetary(
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    housekeeping_status = fields.Selection(
        [
            ("clean", "Clean"),
            ("dirty", "Dirty"),
            ("inspected", "Inspected"),
            ("cleaning", "Cleaning"),
        ],
        default="clean",
        tracking=True,
    )

    state = fields.Selection(
        [
            ("reserved", "Reserved"),
            ("checked_in", "Checked In"),
            ("checked_out", "Checked Out"),
            ("cancelled", "Cancelled"),
        ],
        default="reserved",
        tracking=True,
    )

    service_count = fields.Integer(
        compute="_compute_statistics",
    )

    special_request = fields.Text()

    internal_note = fields.Text()

    @api.depends("adults", "children", "infants")
    def _compute_guest_count(self):
        for record in self:
            record.guest_count = (
                    record.adults
                    + record.children
                    + record.infants
            )

    @api.depends("check_in", "check_out")
    def _compute_nights(self):
        for record in self:
            record.night_count = 0

            if record.check_in and record.check_out:
                delta = (
                        record.check_out.date()
                        - record.check_in.date()
                )

                record.night_count = max(delta.days, 1)

    @api.depends(
        "rate_plan_id",
        "discount_id",
        "night_count",
        "service_ids.total",
    )
    def _compute_amounts(self):

        for line in self:
            line._apply_rate_plan()
            line._apply_discount()
            line._apply_taxes()
            line._apply_services()
            line._compute_total()

    @api.depends("service_ids")
    def _compute_statistics(self):
        for record in self:
            record.service_count = len(record.service_ids)

    @api.onchange("hotel_id")
    def _onchange_hotel(self):

        self.building_id = False
        self.floor_id = False
        self.room_category_id = False
        self.room_id = False

    @api.onchange("building_id")
    def _onchange_building(self):

        self.floor_id = False
        self.room_id = False

    @api.onchange("floor_id")
    def _onchange_floor(self):

        self.room_id = False

    @api.onchange("room_category_id")
    def _onchange_room_category(self):

        self.room_id = False

        if self.hotel_id:
            self.rate_plan_id = self.env[
                "hotel.rate.plan"
            ].search(
                [
                    ("hotel_id", "=", self.hotel_id.id),
                    ("room_category_ids", "in", self.room_category_id.id),
                    ("state", "=", "active"),
                ],
                limit=1,
            )

    @api.onchange("rate_plan_id")
    def _onchange_rate_plan(self):

        if self.rate_plan_id:
            self.base_price = self.rate_plan_id.price

    @api.constrains(
        "adults",
        "children",
        "room_category_id",
    )
    def _check_capacity(self):

        for record in self:

            total = record.adults + record.children

            if (
                    record.room_category_id
                    and total > record.room_category_id.max_occupancy
            ):
                raise ValidationError(
                    _(
                        "Guest count exceeds room capacity."
                    )
                )

    @api.constrains(
        "check_in",
        "check_out",
    )
    def _check_dates(self):

        for record in self:

            if (
                    record.check_in
                    and record.check_out
                    and record.check_in >= record.check_out
            ):
                raise ValidationError(
                    _("Check-out must be after check-in.")
                )

    @api.constrains(
        "room_id",
        "check_in",
        "check_out",
        "state",
    )
    def _check_room_availability(self):

        for record in self:

            if not record.room_id:
                continue

            overlap = self.search(
                [
                    ("id", "!=", record.id),
                    ("room_id", "=", record.room_id.id),
                    ("state", "not in", ["cancelled"]),
                    ("check_in", "<", record.check_out),
                    ("check_out", ">", record.check_in),
                ],
                limit=1,
            )

            if overlap:
                raise ValidationError(
                    _(
                        "This room is already reserved during the selected period."
                    )
                )

    @api.constrains(
        "hotel_id",
        "company_id",
    )
    def _check_company(self):

        for record in self:

            if (
                    record.hotel_id
                    and record.hotel_id.company_id != record.company_id
            ):
                raise ValidationError(
                    _("Company mismatch.")
                )

    def _get_base_price(self):
        """Return the base room price."""

        self.ensure_one()

        if not self.rate_plan_id:
            return 0.0

        return self.rate_plan_id.price

    def _apply_rate_plan(self):
        """Apply selected rate plan."""

        self.ensure_one()

        self.base_price = self._get_base_price()

    def _apply_discount(self):
        """Calculate applicable discount."""

        self.ensure_one()

        self.discount_amount = 0.0

        if not self.discount_id:
            return

        room_total = self.base_price * self.night_count

        if self.discount_id.discount_type == "fixed":
            self.discount_amount = min(
                self.discount_id.discount,
                room_total,
            )

        elif self.discount_id.discount_type == "percentage":
            self.discount_amount = (
                    room_total
                    * self.discount_id.discount
                    / 100
            )

    def _apply_taxes(self):
        """Calculate taxes."""

        self.ensure_one()

        self.tax_amount = 0.0

        taxable_amount = (
                self.base_price * self.night_count
                - self.discount_amount
        )

        # Future:
        # tax_ids.compute_all(...)

    def _apply_services(self):
        """Calculate reservation services."""

        self.ensure_one()

        self.service_amount = sum(
            self.service_ids.mapped("total")
        )

    def _compute_total(self):
        """Calculate reservation totals."""

        self.ensure_one()

        room_total = (
                self.base_price
                * self.night_count
        )

        self.subtotal = (
                room_total
                - self.discount_amount
        )

        self.total = (
                self.subtotal
                + self.tax_amount
                + self.service_amount
        )

    def _validate_booking_period(self):
        """Validate reservation dates."""

        self.ensure_one()

        if not self.check_in:
            raise ValidationError(_("Please select the check-in date."))

        if not self.check_out:
            raise ValidationError(_("Please select the check-out date."))

        if self.check_in >= self.check_out:
            raise ValidationError(
                _("Check-out date must be later than check-in date.")
            )

    def _validate_capacity(self):
        """Validate room occupancy."""

        self.ensure_one()

        if not self.room_category_id:
            return

        total_guests = (
                self.adults
                + self.children
                + self.infants
        )

        if (
                self.room_category_id.max_occupancy
                and total_guests
                > self.room_category_id.max_occupancy
        ):
            raise ValidationError(
                _(
                    "The selected room category '%(room)s' "
                    "allows a maximum of %(capacity)s guests."
                ) % {
                    "room": self.room_category_id.display_name,
                    "capacity": self.room_category_id.max_occupancy,
                }
            )

        if (
                self.room_category_id.max_adults
                and self.adults
                > self.room_category_id.max_adults
        ):
            raise ValidationError(
                _(
                    "The selected room category allows a maximum of %(value)s adults."
                ) % {
                    "value": self.room_category_id.max_adults,
                }
            )

        if (
                self.room_category_id.max_children
                and self.children
                > self.room_category_id.max_children
        ):
            raise ValidationError(
                _(
                    "The selected room category allows a maximum of %(value)s children."
                ) % {
                    "value": self.room_category_id.max_children,
                }
            )

    def _validate_rate_plan(self):
        """Validate selected rate plan."""

        self.ensure_one()

        if not self.rate_plan_id:
            raise ValidationError(
                _("Please select a rate plan.")
            )

        if self.rate_plan_id.state != "active":
            raise ValidationError(
                _("Only active rate plans can be used.")
            )

        if self.rate_plan_id.hotel_id != self.hotel_id:
            raise ValidationError(
                _("The selected rate plan belongs to another hotel.")
            )

        if (
                self.room_category_id
                and self.room_category_id
                not in self.rate_plan_id.room_category_ids
        ):
            raise ValidationError(
                _(
                    "The selected rate plan is not available "
                    "for room category '%s'."
                ) % self.room_category_id.display_name
            )

    def _validate_discount(self):
        """Validate selected discount."""

        self.ensure_one()

        if not self.discount_id:
            return

        if self.discount_id.state != "active":
            raise ValidationError(
                _("Only active discounts can be applied.")
            )

        if self.discount_id.hotel_id != self.hotel_id:
            raise ValidationError(
                _("The selected discount belongs to another hotel.")
            )

        if (
                self.discount_id.date_start
                and self.check_in.date()
                < self.discount_id.date_start
        ):
            raise ValidationError(
                _("The discount is not yet valid.")
            )

        if (
                self.discount_id.date_end
                and self.check_in.date()
                > self.discount_id.date_end
        ):
            raise ValidationError(
                _("The discount has expired.")
            )

    def _validate_room(self):
        """Validate room selection."""

        self.ensure_one()

        if not self.room_id:
            raise ValidationError(
                _("Please select a room.")
            )

        if self.room_id.hotel_id != self.hotel_id:
            raise ValidationError(
                _("The selected room belongs to another hotel.")
            )

        if self.room_id.status == "out_of_order":
            raise ValidationError(
                _("The selected room is out of order.")
            )

        if self.room_id.status == "maintenance":
            raise ValidationError(
                _("The selected room is under maintenance.")
            )




    @api.model
    def _get_reserved_states(self):
        """States that occupy a room."""

        return [
            "reserved",
            "checked_in",
        ]

    def _is_room_available(self):
        """Return True if room is available."""

        self.ensure_one()

        if not self.room_id:
            return False

        ReservationLine = self.env["hotel.reservation.line"]

        overlap = ReservationLine.search_count([
            ("id", "!=", self.id),
            ("room_id", "=", self.room_id.id),
            ("state", "in", self._get_reserved_states()),
            ("check_in", "<", self.check_out),
            ("check_out", ">", self.check_in),
        ])

        return overlap == 0

    @api.constrains(
        "room_id",
        "check_in",
        "check_out",
        "state",
    )
    def _check_room_availability(self):

        for record in self:

            if not record.room_id:
                continue

            if not record._is_room_available():
                raise ValidationError(
                    _(
                        "The selected room is already booked for the selected period."
                    )
                )

    @api.model
    def _get_available_rooms(
            self,
            hotel,
            room_category,
            check_in,
            check_out,
    ):
        """Return available rooms."""

        Room = self.env["hotel.room"]

        rooms = Room.search([
            ("hotel_id", "=", hotel.id),
            ("room_category_id", "=", room_category.id),
            ("active", "=", True),
        ])

        available_rooms = Room.browse()

        for room in rooms:

            overlap = self.search_count([
                ("room_id", "=", room.id),
                ("state", "in", self._get_reserved_states()),
                ("check_in", "<", check_out),
                ("check_out", ">", check_in),
            ])

            if not overlap:
                available_rooms |= room

        return available_rooms

    def _find_alternative_room(self):
        """Suggest another room."""

        self.ensure_one()

        rooms = self._get_available_rooms(
            self.hotel_id,
            self.room_category_id,
            self.check_in,
            self.check_out,
        )

        return rooms[:1]

    def _assign_room(self):
        """Reserve the room."""

        self.ensure_one()

        if self.room_id:
            self.room_id.status = "reserved"

    def _release_room(self):
        """Release reserved room."""

        self.ensure_one()

        if self.room_id:
            self.room_id.status = "available"

    def action_change_room(self, room):
        """Move guest to another room."""

        self.ensure_one()

        self._release_room()

        self.room_id = room

        self._assign_room()

    def _update_room_status(self):
        """Synchronize room status."""

        self.ensure_one()

        if not self.room_id:
            return

        mapping = {
            "reserved": "reserved",
            "checked_in": "occupied",
            "checked_out": "cleaning",
            "cancelled": "available",
        }

        self.room_id.status = mapping.get(
            self.state,
            "available",
        )

    def has_overlap(self):
        """Return whether reservation overlaps."""

        self.ensure_one()

        return not self._is_room_available()

    def _validate_reservation(self):
        """Validate reservation before confirmation."""

        self.ensure_one()

        self._validate_booking_period()

        self._validate_capacity()

        self._validate_rate_plan()

        self._validate_discount()

        self._check_room_availability()

    def _update_reservation(self):

        reservation = self.reservation_id

        reservation._compute_amounts()

        reservation._compute_statistics()

        reservation._compute_state()

    def _validate_reservation_line(self):
        """Validate the reservation line."""

        self.ensure_one()

        self._validate_booking_period()
        self._validate_capacity()
        self._validate_room()
        self._validate_rate_plan()
        self._validate_discount()

        if not self._is_room_available():
            raise ValidationError(
                _(
                    "Room '%s' is not available for the selected dates."
                ) % self.room_id.display_name
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for line in records:
            if line.reservation_id.state not in ("draft",):
                line._validate_reservation_line()

        return records

    def write(self, vals):

        tracked_fields = {
            "room_id",
            "check_in",
            "check_out",
            "rate_plan_id",
            "discount_id",
            "adults",
            "children",
            "infants",
        }

        should_validate = bool(
            tracked_fields.intersection(vals)
        )

        old_rooms = {
            line.id: line.room_id
            for line in self
        }

        result = super().write(vals)

        if should_validate:

            for line in self:

                if line.reservation_id.state != "draft":
                    line._validate_reservation_line()

        return result

    def unlink(self):

        for line in self:

            if line.reservation_id.state not in (
                    "draft",
                    "cancelled",
            ):
                raise UserError(
                    _(
                        "Reservation lines can only be deleted "
                        "while the reservation is in Draft or Cancelled state."
                    )
                )

        return super().unlink()

    def _change_room(self, new_room):
        """Change the room safely."""

        self.ensure_one()

        old_room = self.room_id

        if not new_room:
            raise ValidationError(
                _("Please select a room.")
            )

        self.room_id = new_room

    @api.onchange("room_id")
    def _onchange_room_id(self):
        if not self.room_id:
            return

        if self.hotel_id and self.room_id.hotel_id != self.hotel_id:
            self.room_id = False
            return {
                "warning": {
                    "title": _("Invalid Room"),
                    "message": _(
                        "The selected room does not belong to this hotel."
                    ),
                }
            }

        self.hotel_id = self.room_id.hotel_id
        self.building_id = self.room_id.building_id
        self.floor_id = self.room_id.floor_id
        self.room_category_id = self.room_id.room_category_id

    @api.onchange("room_category_id")
    def _onchange_room_category_id(self):

        if not self.room_category_id:
            self.room_id = False
            self.rate_plan_id = False
            return

        if self.room_id:
            if self.room_id.room_category_id != self.room_category_id:
                self.room_id = False

        self.rate_plan_id = False

        if not self.hotel_id:
            return

        rate_plan = self.env["hotel.rate.plan"].search(
            [
                ("hotel_id", "=", self.hotel_id.id),
                ("room_category_ids", "in", self.room_category_id.id),
                ("state", "=", "active"),
                ("active", "=", True),
            ],
            order="sequence, id",
            limit=1,
        )

        if rate_plan:
            self.rate_plan_id = rate_plan

    @api.onchange("rate_plan_id")
    def _onchange_rate_plan_id(self):

        if not self.rate_plan_id:
            self.base_price = 0.0
            return

        if self.hotel_id and self.rate_plan_id.hotel_id != self.hotel_id:
            self.rate_plan_id = False
            self.base_price = 0.0

            return {
                "warning": {
                    "title": _("Invalid Rate Plan"),
                    "message": _(
                        "The selected rate plan does not belong to this hotel."
                    ),
                }
            }

        if (
                self.room_category_id
                and self.room_category_id
                not in self.rate_plan_id.room_category_ids
        ):
            self.rate_plan_id = False
            self.base_price = 0.0

            return {
                "warning": {
                    "title": _("Invalid Rate Plan"),
                    "message": _(
                        "This rate plan is not available for the selected "
                        "room category."
                    ),
                }
            }

        self.base_price = self._get_base_price()

    @api.onchange("check_in", "check_out")
    def _onchange_booking_dates(self):

        if not self.check_in or not self.check_out:
            return

        if self.check_in >= self.check_out:
            return {
                "warning": {
                    "title": _("Invalid Dates"),
                    "message": _(
                        "Check-out must be later than check-in."
                    ),
                }
            }

        if self.room_id and not self._is_room_available():
            return {
                "warning": {
                    "title": _("Room Unavailable"),
                    "message": _(
                        "The selected room is already booked "
                        "during the selected period."
                    ),
                }
            }

    @api.onchange(
        "adults",
        "children",
        "infants",
    )
    def _onchange_guests(self):

        if not self.room_category_id:
            return

        total_guests = (
                self.adults
                + self.children
                + self.infants
        )

        capacity = self.room_category_id.maximum_occupancy

        if capacity and total_guests > capacity:
            return {
                "warning": {
                    "title": _("Room Capacity Exceeded"),
                    "message": _(
                        "This room category allows a maximum of %s guests."
                    ) % capacity,
                }
            }

