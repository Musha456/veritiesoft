from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

from server.odoo.tools.view_validation import relaxng


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
        related="reservation_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    reservation_id = fields.Many2one(
        "hotel.reservation",
        required=True,
        ondelete="cascade",
        index=True,
    )

    hotel_id = fields.Many2one(
        "hotel.hotel",
        related="reservation_id.hotel_id",
        store=True,
        readonly=True,
    )

    building_id = fields.Many2one(
        "hotel.building",
        domain="[('hotel_id','=',hotel_id)]",
    )

    floor_id = fields.Many2one(
        "hotel.building.floor",
        domain="[('building_id','=',building_id)]",
    )

    room_category_id = fields.Many2one(
        "hotel.room.category",
        required=True,
    )

    room_id = fields.Many2one(
        "hotel.room",
        string="Room",
        required=True,
    )

    # room_id = fields.Many2one(
    #     "hotel.room",
    #     required=True,
    #     domain="""
    #        [
    #            ('building_id','=',building_id),
    #            ('floor_id','=',floor_id),
    #            ('room_category_id','=',room_category_id),
    #            ('status','=','available')
    #        ]
    #        """,
    # )

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

    check_in = fields.Datetime(
        related="reservation_id.check_in",
        store=True,
        readonly=False,
    )

    check_out = fields.Datetime(
        related="reservation_id.check_out",
        store=True,
        readonly=False,
    )

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

    rate_plan_id = fields.Many2one(
        "hotel.rate.plan",
        required=True,
    )

    room_price = fields.Monetary(
        related="rate_plan_id.base_price",
        string="Room Price",
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


    discount_id = fields.Many2one(
        "hotel.discount",
    )

    service_amount = fields.Monetary(
        string="Service Amount",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )

    discount_amount = fields.Monetary(
        string="Room Discount",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )

    service_line_discounts = fields.Monetary(
        string="Service Discount",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )

    total_discount_amount = fields.Monetary(
        string="Total Discount Amount",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )

    tax_amount = fields.Monetary(
        string="Room Tax Amount",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )

    tax_ids = fields.Many2many(
        "account.tax",
        string="Taxes",
    )

    total_tax_amount = fields.Monetary(
        string="Tax",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )

    subtotal = fields.Monetary(
        string="Subtotal",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )

    room_amount = fields.Monetary(
        string="Room Amount",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )

    total = fields.Monetary(
        string="Total",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )

    service_line_ids = fields.One2many(
        "hotel.reservation.service.line",
        "reservation_line_id",
        string="Services",
    )

    room_booking_id = fields.Many2one(
        "hotel.room.booking",
        string="Room Booking",
        readonly=True,
        copy=False,
        ondelete="set null",
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

    service_tax_amount = fields.Monetary(
        string="Service Tax Amount",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )

    room_domain = fields.Binary(
        compute="_compute_room_domain",
    )

    special_request = fields.Text()

    note = fields.Text()

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
        "tax_ids",

        "service_line_ids",
        "service_line_ids.quantity",
        "service_line_ids.price_unit",
        "service_line_ids.discount_id",
        "service_line_ids.discount_amount",
        "service_line_ids.tax_ids",
        "service_line_ids.tax_amount",
        "service_line_ids.subtotal",
        "service_line_ids.total",
    )
    def _compute_amounts(self):
        for line in self:
            line._apply_rate_plan()
            line._apply_discount()
            line._apply_services()
            line._apply_taxes()
            line._compute_total()

    @api.depends("service_line_ids")
    def _compute_statistics(self):
        for record in self:
            record.service_count = len(record.service_line_ids)

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

    @api.depends(
        "hotel_id",
        "building_id",
        "floor_id",
        "room_category_id",
        "check_in",
        "check_out",
        "reservation_id.line_ids.room_id",
    )
    def _compute_room_domain(self):
        for line in self:
            domain = [
                ("active", "=", True),
                ("status", "=", "available"),
            ]

            # Hotel
            if line.hotel_id:
                domain.append(
                    ("hotel_id", "=", line.hotel_id.id)
                )

            # Building
            if line.building_id:
                domain.append(
                    ("building_id", "=", line.building_id.id)
                )

            # Floor
            if line.floor_id:
                domain.append(
                    ("floor_id", "=", line.floor_id.id)
                )

            # Room Category
            if line.room_category_id:
                domain.append(
                    (
                        "room_category_id",
                        "=",
                        line.room_category_id.id,
                    )
                )

            # Rooms already selected in this reservation
            if line.reservation_id:
                selected_room_ids = (
                    line.reservation_id.line_ids
                    .filtered(
                        lambda l: l.id != line.id and l.room_id
                    )
                    .mapped("room_id")
                    .ids
                )

                if selected_room_ids:
                    domain.append(
                        ("id", "not in", selected_room_ids)
                    )

            # Rooms already booked for the selected period
            if (
                    line.check_in
                    and line.check_out
                    and line.check_out > line.check_in
            ):
                booked_room_ids = self.env[
                    "hotel.room.booking"
                ].search(
                    [
                        ("check_in", "<", line.check_out),
                        ("check_out", ">", line.check_in),
                        (
                            "state",
                            "not in",
                            ("cancelled", "released"),
                        ),
                    ]
                ).mapped("room_id").ids

                if booked_room_ids:
                    domain.append(
                        ("id", "not in", booked_room_ids)
                    )

            line.room_domain = domain

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

        for line in self:
            if (
                    line.room_id
                    and line.room_category_id
                    and line.room_id.room_category_id
                    != line.room_category_id
            ):
                line.room_id = False

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
    )
    def _check_room_availability(self):
        for line in self:

            if not line.room_id:
                continue

            if not line.check_in or not line.check_out:
                continue

            if line.check_out <= line.check_in:
                continue

            booking = line.room_booking_id

            if not line.room_id._is_available_for_period(
                    line.check_in,
                    line.check_out,
                    exclude_booking=booking,
            ):
                raise ValidationError(
                    _(
                        "Room %s is not available from %s to %s."
                    )
                    % (
                        line.room_id.display_name,
                        line.check_in,
                        line.check_out,
                    )
                )

    # @api.constrains(
    #     "hotel_id",
    #     "company_id",
    # )
    # def _check_company(self):
    #
    #     for record in self:
    #
    #         if (
    #                 record.hotel_id
    #                 and record.hotel_id.company_id != record.company_id
    #         ):
    #             raise ValidationError(
    #                 _("Company mismatch.")
    #             )

    def _get_base_price(self):
        """Return the base room price."""

        self.ensure_one()

        if not self.rate_plan_id:
            return 0.0

        return self.rate_plan_id.base_price

    def _apply_rate_plan(self):
        """Apply selected rate plan."""

        self.ensure_one()

        self.room_amount = self._get_base_price() * self.night_count

    def _apply_discount(self):
        """Calculate applicable discount."""
        self.ensure_one()

        self.discount_amount = 0.0
        self.service_line_discounts = 0.0
        self.total_discount_amount = 0.0

        if not self.discount_id:
            return

        room_total = self.room_amount
        discount_amount = 0.0

        if self.discount_id.discount_type == "fixed":
            discount_amount = min(
                self.discount_id.discount,
                room_total,
            )

        elif self.discount_id.discount_type == "percentage":
            discount_amount = (
                    room_total * self.discount_id.discount / 100
            )

        service_line_discounts = sum(
            self.service_line_ids.mapped("discount_amount")
        )

        self.discount_amount = discount_amount
        self.service_line_discounts = service_line_discounts
        self.total_discount_amount = (
                discount_amount + service_line_discounts
        )


    def _apply_taxes(self):
        for line in self:

            taxable_amount = (line.room_amount - line.total_discount_amount)

            # Calculate taxes applicable to the room/rate.
            # Do NOT include service_line taxes here.

            line.tax_amount = 0.0

            # for line in self:
            #     service_lines = line.service_line_ids
            #
            #     service_line_discounts = sum(service_lines.mapped("discount_amount"))

            if line.tax_ids:
                taxes = line.tax_ids.compute_all(
                    taxable_amount,
                    currency=line.currency_id,
                    quantity=1.0,
                    product=False,
                    partner=line.reservation_id.partner_id,
                )

                line.tax_amount = (
                        taxes["total_included"]
                        - taxes["total_excluded"]
                )

    def _apply_services(self):
        for line in self:
            service_lines = line.service_line_ids
            line.service_amount = sum(service_lines.mapped("subtotal"))
            line.service_tax_amount = sum(service_lines.mapped("tax_amount"))

    def _compute_total(self):
        for line in self:
            line.subtotal = (line.room_amount - line.total_discount_amount + line.service_amount)
            total_tax_amount = line.tax_amount + line.service_tax_amount
            self.total_tax_amount = total_tax_amount
            line.total = (line.subtotal + total_tax_amount)

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
                        "Room '%s' is not available for the selected period."
                    ) % record.room_id.display_name
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

    @api.onchange("rate_plan_id")
    def _onchange_rate_plan_id(self):
        for line in self:
            if line.rate_plan_id:
                line._apply_rate_plan()
                line._apply_discount()
                line._apply_taxes()
                line._apply_services()
                line._compute_total()

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

        capacity = self.room_category_id.max_occupancy

        if capacity and total_guests > capacity:
            return {
                "warning": {
                    "title": _("Room Capacity Exceeded"),
                    "message": _(
                        "This room category allows a maximum of %s guests."
                    ) % capacity,
                }
            }

    @api.onchange(
        "hotel_id",
        "room_category_id",
        "check_in",
        "check_out",
    )
    def _onchange_room_availability(self):
        for line in self:

            line.room_id = False

            domain = [
                ("active", "=", True),
            ]

            if line.hotel_id:
                domain.append(
                    ("hotel_id", "=", line.hotel_id.id)
                )

            if line.room_category_id:
                domain.append(
                    (
                        "room_category_id",
                        "=",
                        line.room_category_id.id,
                    )
                )

            if (
                    not line.check_in
                    or not line.check_out
                    or line.check_out <= line.check_in
            ):
                return {
                    "domain": {
                        "room_id": domain,
                    }
                }

            rooms = self.env["hotel.room"].search(domain)

            available_rooms = rooms.filtered(
                lambda room: room._is_available_for_period(
                    line.check_in,
                    line.check_out,
                    exclude_booking=line.room_booking_id,
                )
            )

            return {
                "domain": {
                    "room_id": [
                        ("id", "in", available_rooms.ids),
                    ],
                }
            }

    # ---------------------------------------------------------
    # ROOM BOOKING
    # ---------------------------------------------------------

    def _create_room_booking(self):
        RoomBooking = self.env["hotel.room.booking"]

        bookings = self.env["hotel.room.booking"]

        for line in self:

            if line.room_booking_id:
                bookings |= line.room_booking_id
                continue

            if not line.room_id:
                raise ValidationError(
                    _(
                        "Please select a room before creating "
                        "the room booking."
                    )
                )

            if not line.check_in or not line.check_out:
                raise ValidationError(
                    _(
                        "Check-in and check-out dates are required "
                        "before creating the room booking."
                    )
                )

            if line.check_out <= line.check_in:
                raise ValidationError(
                    _("Check-out must be later than check-in.")
                )

            line._validate_capacity()
            line._validate_rate_plan()

            booking = RoomBooking.create({
                "reservation_id": line.reservation_id.id,
                "reservation_line_id": line.id,
                "guest_id": line.reservation_id.partner_id.id,
                "hotel_id": line.hotel_id.id,
                "room_id": line.room_id.id,
                "room_category_id": line.room_category_id.id,
                "check_in": line.check_in,
                "check_out": line.check_out,
                "company_id": line.company_id.id,
            })

            line.room_booking_id = booking.id

            bookings |= booking

        return bookings


    def _release_room_booking(self):
        """
        Release a reserved room booking.

        The booking record is preserved for history.
        """

        self.ensure_one()

        booking = self.room_booking_id

        if not booking:
            return

        if booking.state == "reserved":
            booking.action_release()

    # ---------------------------------------------------------
    # CANCEL ROOM BOOKING
    # ---------------------------------------------------------

    def _cancel_room_booking(self):
        """
        Cancel a reserved room booking.

        The booking record is preserved.
        """

        self.ensure_one()

        booking = self.room_booking_id

        if not booking:
            return

        # if booking.state == "reserved":
        booking.action_cancel()

    # ---------------------------------------------------------
    # CHECK IN
    # ---------------------------------------------------------

    def _check_in_room_booking(self):
        """
        Check the guest into the physical room.
        """

        self.ensure_one()

        booking = self.room_booking_id

        if not booking:
            booking = self._create_room_booking()

        if booking.state != "reserved":
            raise UserError(
                _(
                    "Room '%s' is not in a reserved state."
                )
                % self.room_id.display_name
            )

        booking.action_check_in()

    # ---------------------------------------------------------
    # CHECK OUT
    # ---------------------------------------------------------

    def _check_out_room_booking(self):
        """
        Check the guest out of the physical room.
        """

        self.ensure_one()

        booking = self.room_booking_id

        if not booking:
            raise UserError(
                _(
                    "No room booking exists for room '%s'."
                )
                % self.room_id.display_name
            )

        if booking.state != "checked_in":
            raise UserError(
                _(
                    "Room '%s' is not currently checked in."
                )
                % self.room_id.display_name
            )

        booking.action_check_out()

    # ---------------------------------------------------------
    # ROOM BOOKING VALIDATION
    # ---------------------------------------------------------

    def _validate_room_booking(self):
        """
        Validate that this line has everything required
        to create a physical room booking.
        """

        self.ensure_one()

        if not self.room_id:
            raise ValidationError(
                _(
                    "A room is required for reservation line '%s'."
                )
                % self.display_name
            )

        if not self.check_in:
            raise ValidationError(
                _(
                    "Check-in is required for reservation line '%s'."
                )
                % self.display_name
            )

        if not self.check_out:
            raise ValidationError(
                _(
                    "Check-out is required for reservation line '%s'."
                )
                % self.display_name
            )

        if self.check_out <= self.check_in:
            raise ValidationError(
                _(
                    "Check-out must be later than check-in."
                )
            )

        self._validate_capacity()
        self._validate_rate_plan()

    # ---------------------------------------------------------
    # WRITE
    # ---------------------------------------------------------
    def write(self, vals):

        protected_fields = {
            "hotel_id",
            "building_id",
            "floor_id",
            "room_category_id",
            "room_id",
            "rate_plan_id",
            "check_in",
            "check_out",
        }

        locked_states = (
            "reserved",
            "checked_in",
            "checked_out",
            "completed",
            "cancelled",
            "no_show",
        )

        service_locked_states = (
            "checked_out",
            "completed",
            "cancelled",
            "no_show",
        )

        for line in self:

            reservation = line.reservation_id

            if not reservation:
                continue

            # =====================================================
            # ROOM / RESERVATION LINE FIELDS
            # =====================================================

            if (
                    protected_fields.intersection(vals.keys())
                    and reservation.state in locked_states
            ):
                raise UserError(
                    _(
                        "Room information cannot be modified after "
                        "the reservation becomes operational."
                    )
                )

            # =====================================================
            # SERVICE LINES
            # =====================================================

            if (
                    "service_line_ids" in vals
                    and reservation.state in service_locked_states
            ):
                raise UserError(
                    _(
                        "Services cannot be modified after "
                        "the reservation is closed."
                    )
                )

        return super().write(vals)
    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------

    def unlink(self):

        for line in self:

            if line.room_booking_id and line.room_booking_id.state in (
                    "checked_in",
                    "checked_out",
            ):
                raise UserError(
                    _(
                        "A reservation line cannot be deleted after "
                        "the room has been checked in or checked out."
                    )
                )

        return super().unlink()

    def _sync_room_booking(self):
        for line in self:

            booking = line.room_booking_id

            # No room booking exists yet.
            if not booking:
                continue

            # Do not modify completed/cancelled/released bookings.
            if booking.state in (
                    "checked_out",
                    "completed",
                    "released",
                    "cancelled",
            ):
                raise ValidationError(
                    _(
                        "The room booking %s can no longer be modified."
                    ) % booking.display_name
                )

            if not line.room_id:
                raise ValidationError(
                    _("A room is required for the room booking.")
                )

            if not line.check_in or not line.check_out:
                raise ValidationError(
                    _(
                        "Check-in and check-out dates are required "
                        "for the room booking."
                    )
                )

            if line.check_out <= line.check_in:
                raise ValidationError(
                    _("Check-out must be later than check-in.")
                )

            # Validate the new room/date combination
            # before changing the existing booking.
            overlapping_booking = self.env[
                "hotel.room.booking"
            ].search(
                [
                    ("id", "!=", booking.id),
                    ("room_id", "=", line.room_id.id),
                    (
                        "state",
                        "not in",
                        ("cancelled", "released"),
                    ),
                    ("check_in", "<", line.check_out),
                    ("check_out", ">", line.check_in),
                ],
                limit=1,
            )

            if overlapping_booking:
                raise ValidationError(
                    _(
                        "Room %(room)s is already booked from "
                        "%(start)s to %(end)s."
                    )
                    % {
                        "room": line.room_id.display_name,
                        "start": overlapping_booking.check_in,
                        "end": overlapping_booking.check_out,
                    }
                )

            booking.write({
                "hotel_id": line.hotel_id.id,
                "room_id": line.room_id.id,
                "room_category_id": line.room_category_id.id,
                "check_in": line.check_in,
                "check_out": line.check_out,
                "guest_id": line.reservation_id.partner_id.id,
            })

    @api.depends("check_in", "check_out")
    def _compute_night_count(self):
        for line in self:
            if line.check_in and line.check_out:
                duration = line.check_out - line.check_in
                line.night_count = max(
                    0,
                    duration.days,
                )
            else:
                line.night_count = 0

    @api.constrains(
        "check_in",
        "check_out",
        "adults",
        "children",
    )
    def _check_reservation_line(self):
        for line in self:

            if (
                    line.check_in
                    and line.check_out
                    and line.check_out <= line.check_in
            ):
                raise ValidationError(
                    _(
                        "Check-out must be later than check-in."
                    )
                )

            if line.adults < 1:
                raise ValidationError(
                    _("At least one adult is required.")
                )

            if line.children < 0:
                raise ValidationError(
                    _("Children count cannot be negative.")
                )

    @api.onchange("reservation_id")
    def _onchange_reservation_id(self):
        for line in self:
            if not line.reservation_id:
                continue

            reservation = line.reservation_id

            line.hotel_id = reservation.hotel_id

            if reservation.check_in:
                line.check_in = reservation.check_in

            if reservation.check_out:
                line.check_out = reservation.check_out


    @api.onchange(
        "room_category_id",
        "adults",
        "children",
    )
    def _onchange_capacity(self):
        for line in self:

            if not line.room_category_id:
                continue

            if (
                    line.adults
                    > line.room_category_id.max_adults
            ):
                return {
                    "warning": {
                        "title": _("Adult Capacity Exceeded"),
                        "message": _(
                            "This room category allows a maximum "
                            "of %s adults."
                        )
                                   % line.room_category_id.max_adults,
                    }
                }

            if (
                    line.children
                    > line.room_category_id.max_children
            ):
                return {
                    "warning": {
                        "title": _("Child Capacity Exceeded"),
                        "message": _(
                            "This room category allows a maximum "
                            "of %s children."
                        )
                                   % line.room_category_id.max_children,
                    }
                }