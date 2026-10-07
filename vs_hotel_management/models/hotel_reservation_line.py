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
        string="Total Discount",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )

    tax_amount = fields.Monetary(
        string="Room Tax",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )

    tax_ids = fields.Many2many(
        "account.tax",
        string="Taxes",
    )

    product_id = fields.Many2one(
        "product.product",
        string="Room Product",
        related="room_id.room_category_id.product_id",
        store=True,
        readonly=True,
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
        related="reservation_id.state",
        string="Status",
        store=True,
        readonly=True,
        index=True,
    )

    service_count = fields.Integer(
        compute="_compute_statistics",
    )

    service_tax_amount = fields.Monetary(
        string="Service Tax",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )

    available_room_ids = fields.Many2many(
        "hotel.room",
        compute="_compute_available_room_ids",
        string="Available Rooms",
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
        if self.building_id and self.building_id.hotel_id != self.hotel_id:
            self.building_id = False
            self.floor_id = False
            self.room_id = False

    @api.onchange("building_id")
    def _onchange_building(self):
        if self.floor_id and self.floor_id.building_id != self.building_id:
            self.floor_id = False
        if self.room_id and self.room_id.building_id != self.building_id:
            self.room_id = False

    @api.onchange("floor_id")
    def _onchange_floor(self):
        if self.room_id and self.room_id.floor_id != self.floor_id:
            self.room_id = False

    @api.depends(
        "hotel_id",
        "building_id",
        "floor_id",
        "room_category_id",
        "check_in",
        "check_out",
        "adults",
        "children",
        "infants",
        "room_id",
        "reservation_id.line_ids.room_id",
        "reservation_id.line_ids.check_in",
        "reservation_id.line_ids.check_out",
        "reservation_id.check_in",
        "reservation_id.check_out",
    )
    def _compute_available_room_ids(self):
        for line in self:
            domain = [
                ("active", "=", True),
                ("status", "not in", ("out_of_order", "maintenance")),
            ]

            hotel_id = line.hotel_id or (
                    line.reservation_id and line.reservation_id.hotel_id
            )

            if hotel_id:
                domain.append(("hotel_id", "=", hotel_id.id))

            if line.building_id:
                domain.append(("building_id", "=", line.building_id.id))

            if line.floor_id:
                domain.append(("floor_id", "=", line.floor_id.id))

            if line.room_category_id:
                domain.append(
                    ("room_category_id", "=", line.room_category_id.id)
                )

            rooms = self.env["hotel.room"].search(domain)

            # Filter by guest capacity
            total_guests = line.adults + line.children

            if total_guests > 0:
                rooms = rooms.filtered(
                    lambda r: (
                            (
                                    not r.room_category_id.max_occupancy
                                    or total_guests <= r.room_category_id.max_occupancy
                            )
                            and (
                                    not r.room_category_id.max_adults
                                    or line.adults <= r.room_category_id.max_adults
                            )
                            and (
                                    not r.room_category_id.max_children
                                    or line.children <= r.room_category_id.max_children
                            )
                    )
                )

            check_in = line.check_in or (
                    line.reservation_id and line.reservation_id.check_in
            )
            check_out = line.check_out or (
                    line.reservation_id and line.reservation_id.check_out
            )

            # Check date-based availability
            if check_in and check_out and check_out > check_in:

                # 1. Overlap with active room bookings
                booking_domain = [
                    ("room_id", "in", rooms.ids),
                    ("state", "in", ("reserved", "checked_in")),
                    ("check_in", "<", check_out),
                    ("check_out", ">", check_in),
                ]

                if line.room_booking_id and line.room_booking_id._origin.id:
                    booking_domain.append(
                        ("id", "!=", line.room_booking_id._origin.id)
                    )

                if line.reservation_id and line.reservation_id._origin.id:
                    booking_domain.append(
                        (
                            "reservation_id",
                            "!=",
                            line.reservation_id._origin.id,
                        )
                    )

                booked_room_ids = set(
                    self.env["hotel.room.booking"]
                    .search(booking_domain)
                    .mapped("room_id")
                    .ids
                )

                # 2. Overlap with other reservation lines
                res_line_domain = [
                    ("room_id", "in", rooms.ids),
                    (
                        "reservation_id.state",
                        "in",
                        ("confirmed", "reserved", "checked_in"),
                    ),
                    ("check_in", "<", check_out),
                    ("check_out", ">", check_in),
                ]

                if line.reservation_id and line.reservation_id._origin.id:
                    res_line_domain.append(
                        (
                            "reservation_id",
                            "!=",
                            line.reservation_id._origin.id,
                        )
                    )

                if line._origin.id:
                    res_line_domain.append(
                        ("id", "!=", line._origin.id)
                    )

                other_res_room_ids = set(
                    self.env["hotel.reservation.line"]
                    .search(res_line_domain)
                    .mapped("room_id")
                    .ids
                )

                # 3. Exclude rooms already selected on other lines
                # of the same reservation for overlapping dates.
                same_res_room_ids = set()

                if line.reservation_id:
                    other_lines = line.reservation_id.line_ids.filtered(
                        lambda l: (
                                l != line
                                and l.room_id
                        )
                    )

                    for ol in other_lines:
                        ol_in = ol.check_in or line.reservation_id.check_in
                        ol_out = ol.check_out or line.reservation_id.check_out

                        if (
                                ol_in
                                and ol_out
                                and ol_in < check_out
                                and ol_out > check_in
                        ):
                            same_res_room_ids.add(ol.room_id.id)

                unavailable_room_ids = (
                        booked_room_ids
                        | other_res_room_ids
                        | same_res_room_ids
                )

                # 4. If reservation is currently in progress,
                # exclude rooms that are operationally unavailable.
                now = fields.Datetime.now()

                if check_in <= now < check_out:
                    curr_unavail = rooms.filtered(
                        lambda r: r.status in (
                            "occupied",
                            "cleaning",
                            "dirty",
                        )
                    )
                    unavailable_room_ids |= set(curr_unavail.ids)

                rooms = rooms.filtered(
                    lambda r: r.id not in unavailable_room_ids
                )

            # Keep the current selected room if it is still valid.
            if line.room_id and line.room_id not in rooms:
                if line.room_id.active and line.room_id.status not in (
                        "out_of_order",
                        "maintenance",
                ):
                    if line._is_room_available():
                        rooms |= line.room_id

            line.available_room_ids = rooms

    @api.onchange("room_category_id")
    def _onchange_room_category(self):
        if self.room_id and self.room_id.room_category_id != self.room_category_id:
            self.room_id = False

        if self.hotel_id and self.room_category_id:
            self.rate_plan_id = self.env["hotel.rate.plan"].search(
                [
                    ("hotel_id", "=", self.hotel_id.id),
                    ("room_category_ids", "in", self.room_category_id.id),
                    ("state", "=", "active"),
                ],
                limit=1,
            )

    @api.constrains(
        "adults",
        "children",
        "infants",
        "room_category_id",
        "room_id",
    )
    def _check_capacity(self):
        for record in self:
            record._validate_capacity()

    @api.constrains("room_id", "room_category_id")
    def _check_room_category_match(self):
        for line in self:
            if line.room_id and line.room_category_id:
                if line.room_id.room_category_id != line.room_category_id:
                    raise ValidationError(
                        _(
                            "The selected room '%(room)s' does not belong to the selected room type '%(category)s'."
                        )
                        % {
                            "room": line.room_id.display_name,
                            "category": line.room_category_id.display_name,
                        }
                    )

    @api.constrains("room_id")
    def _check_room_operational_status(self):
        for line in self:
            if not line.room_id:
                continue
            if line.reservation_id and line.reservation_id.state in ("cancelled", "no_show"):
                continue
            if line.room_id.status == "out_of_order":
                raise ValidationError(_("Room '%s' is out of order.") % line.room_id.display_name)
            if line.room_id.status == "maintenance":
                raise ValidationError(
                    _("Room '%s' is currently unavailable due to maintenance.") % line.room_id.display_name
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

        room_total = self.room_amount
        discount_amount = 0.0

        if self.discount_id:
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

    @api.depends(
        "room_amount",
        "discount_amount",
        "tax_ids",
    )
    def _apply_taxes(self):
        for line in self:
            taxable_amount = line.room_amount - line.discount_amount

            print("Tax Ids", line.tax_ids)
            print("Taxable Amount", taxable_amount)

            tax_amount = 0.0

            if line.tax_ids and taxable_amount > 0:
                taxes = line.tax_ids.compute_all(
                    taxable_amount,
                    currency=line.currency_id,
                    quantity=1.0,
                    product=False,
                    partner=line.reservation_id.partner_id,
                )

                tax_amount = (
                        taxes["total_included"]
                        - taxes["total_excluded"]
                )

            line.tax_amount = tax_amount

    @api.depends(
        "service_line_ids",
        "service_line_ids.quantity",
        "service_line_ids.price_unit",
        "service_line_ids.subtotal",
        "service_line_ids.tax_amount",
        "service_line_ids.discount_amount",
    )
    def _apply_services(self):
        for line in self:
            service_lines = line.service_line_ids

            line.service_amount = sum(
                service_line.quantity * service_line.price_unit
                for service_line in service_lines
            )

            line.service_tax_amount = sum(
                service_lines.mapped("tax_amount")
            )

    @api.depends(
        "room_amount",
        "discount_amount",
        "service_amount",
        "service_line_ids.discount_amount",
        "tax_amount",
        "service_tax_amount",
    )
    def _compute_total(self):
        for line in self:
            room_discount = line.discount_amount
            service_discount = sum(
                line.service_line_ids.mapped("discount_amount")
            )

            line.total_discount_amount = (
                    room_discount + service_discount
            )

            line.subtotal = (
                    line.room_amount
                    + line.service_amount
                    - line.total_discount_amount
            )

            line.total_tax_amount = (
                    line.tax_amount
                    + line.service_tax_amount
            )

            line.total = (
                    line.subtotal
                    + line.total_tax_amount
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

        category = self.room_category_id or (self.room_id and self.room_id.room_category_id)
        if not category:
            return

        total_guests = (
                self.adults
                + self.children
        )

        if (
                category.max_occupancy
                and total_guests
                > category.max_occupancy
        ):
            raise ValidationError(
                _(
                    "The selected room cannot accommodate the specified number of guests."
                )
            )

        if (
                category.max_adults
                and self.adults
                > category.max_adults
        ):
            raise ValidationError(
                _(
                    "The selected room category allows a maximum of %s adults."
                ) % category.max_adults
            )

        if (
                category.max_children
                and self.children
                > category.max_children
        ):
            raise ValidationError(
                _(
                    "The selected room category allows a maximum of %s children."
                ) % category.max_children
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

        if self.room_category_id and self.room_id.room_category_id != self.room_category_id:
            raise ValidationError(
                _(
                    "The selected room '%(room)s' does not belong to the selected room type '%(category)s'."
                )
                % {
                    "room": self.room_id.display_name,
                    "category": self.room_category_id.display_name,
                }
            )

        if self.room_id.status == "out_of_order":
            raise ValidationError(
                _("Room '%s' is out of order.") % self.room_id.display_name
            )

        if self.room_id.status == "maintenance":
            raise ValidationError(
                _("Room '%s' is currently unavailable due to maintenance.") % self.room_id.display_name
            )

    @api.model
    def _get_reserved_states(self):
        """States that occupy a room."""
        return [
            "confirmed",
            "reserved",
            "checked_in",
        ]

    def _is_room_available(self, raise_exception=False, for_check_in=False):
        """Return True if room is available for the period."""
        self.ensure_one()
        if not self.room_id:
            if raise_exception:
                raise ValidationError(_("Please select a room."))
            return False

        check_in = self.check_in or (self.reservation_id and self.reservation_id.check_in)
        check_out = self.check_out or (self.reservation_id and self.reservation_id.check_out)

        return self.room_id.is_available(
            check_in=check_in,
            check_out=check_out,
            current_reservation=self.reservation_id,
            current_line=self,
            exclude_booking=self.room_booking_id,
            for_check_in=for_check_in,
            raise_exception=raise_exception,
        )

    # def _is_room_available(self, raise_exception=False, for_check_in=False):
    #     self.ensure_one()
    #
    #     print("========== ROOM AVAILABILITY DEBUG ==========")
    #     print("Line ID:", self.id)
    #     print("Room:", self.room_id)
    #     print("Room ID:", self.room_id.id)
    #     print("Room Status:", self.room_id.status)
    #     print("Room Active:", self.room_id.active)
    #     print("Check In:", self.check_in)
    #     print("Check Out:", self.check_out)
    #     print("Reservation:", self.reservation_id)
    #     print("Reservation ID:", self.reservation_id.id if self.reservation_id else None)
    #     print("Room Booking:", self.room_booking_id)
    #     print("Room Booking ID:", self.room_booking_id.id if self.room_booking_id else None)
    #     print("==============================================")
    #
    #     if not self.room_id:
    #         print("RESULT: FALSE -> NO ROOM")
    #         return False
    #
    #     check_in = self.check_in or (
    #             self.reservation_id and self.reservation_id.check_in
    #     )
    #     check_out = self.check_out or (
    #             self.reservation_id and self.reservation_id.check_out
    #     )
    #
    #     print("Final Check In:", check_in)
    #     print("Final Check Out:", check_out)
    #
    #     result = self.room_id.is_available(
    #         check_in=check_in,
    #         check_out=check_out,
    #         current_reservation=self.reservation_id,
    #         current_line=self,
    #         exclude_booking=self.room_booking_id,
    #         for_check_in=for_check_in,
    #         raise_exception=raise_exception,
    #     )
    #
    #     print("FINAL is_available RESULT:", result)
    #     print("==============================================")
    #
    #     return result

    @api.constrains(
        "room_id",
        "check_in",
        "check_out",
        "state",
    )
    def _check_room_availability(self):
        for record in self:
            if not record.room_id or not record.check_in or not record.check_out:
                continue

            # Do not validate inactive/completed reservation states.
            # Draft reservations must still validate the selected room,
            # but they should not themselves block room availability.
            if record.reservation_id and record.reservation_id.state in (
                    "cancelled",
                    "no_show",
                    "completed",
                    "checked_out",
            ):
                continue

            allow_overbooking = False
            if record.hotel_id:
                allow_overbooking = record.hotel_id.allow_overbooking
            if not allow_overbooking:
                param = self.env["ir.config_parameter"].sudo().get_param(
                    "vs_hotel_management.allow_overbooking", default="False"
                )
                allow_overbooking = param in (True, "True", "1")

            if not allow_overbooking:
                record._is_room_available(raise_exception=True)

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
            ("status", "not in", ("out_of_order", "maintenance")),
        ])

        available_rooms = Room.browse()

        for room in rooms:
            if room._is_available_for_period(check_in, check_out):
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

        self._validate_reservation_line()

    def _update_reservation(self):

        reservation = self.reservation_id

        reservation._compute_amounts()

        reservation._compute_statistics()

        reservation._compute_state()

    def _validate_reservation_line(self, for_check_in=False, allow_overbooking=False):
        """Validate the reservation line."""

        self.ensure_one()

        self._validate_booking_period()
        self._validate_capacity()
        self._validate_room()
        self._validate_rate_plan()
        self._validate_discount()

        if not allow_overbooking:
            self._is_room_available(raise_exception=True, for_check_in=for_check_in)

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

        if self.room_category_id and self.room_id.room_category_id != self.room_category_id:
            self.room_id = False
            return {
                "warning": {
                    "title": _("Invalid Room Type"),
                    "message": _(
                        "The selected room does not belong to the selected room type."
                    ),
                }
            }

        self.hotel_id = self.room_id.hotel_id
        self.building_id = self.room_id.building_id
        self.floor_id = self.room_id.floor_id
        if not self.room_category_id:
            self.room_category_id = self.room_id.room_category_id

        # Auto-assign active rate plan if not set or mismatched
        if self.hotel_id and self.room_category_id:
            if not self.rate_plan_id or self.room_category_id not in self.rate_plan_id.room_category_ids:
                rate_plan = self.env["hotel.rate.plan"].search(
                    [
                        ("hotel_id", "=", self.hotel_id.id),
                        ("room_category_ids", "in", self.room_category_id.id),
                        ("state", "=", "active"),
                    ],
                    limit=1,
                )
                if rate_plan:
                    self.rate_plan_id = rate_plan.id

        if self.room_id.room_category_id.product_id:
            self.tax_ids = self.room_id.room_category_id.product_id.taxes_id

        self._compute_amounts()

        print("Check in",self.check_in)
        print("Check out",self.check_out)
        print("Room available",self._is_room_available())

        if self.check_in and self.check_out and not self._is_room_available():
            room_name = self.room_id.display_name
            self.room_id = False

            return {
                "warning": {
                    "title": _("Room Unavailable"),
                    "message": _(
                        "The selected room '%s' is not available for the selected dates."
                    ) % room_name,
                }
            }

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
                        "The selected room '%s' is not available "
                        "during the selected period."
                    ) % self.room_id.display_name,
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
                        "in",
                        ("reserved", "checked_in"),
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
