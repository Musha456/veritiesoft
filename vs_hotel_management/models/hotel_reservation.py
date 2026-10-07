import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError, AccessError
from odoo import Command
from psycopg2 import IntegrityError


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
        string="Reservation Reference",
        required=True,
        readonly=True,
        copy=False,
        default="/",
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

    guest_phone = fields.Char(related="partner_id.phone", sring="Guest Phone")

    guest_email = fields.Char(
        related="partner_id.email",
        string="Guest Email",
    )

    id_type = fields.Selection(
        [
            ("passport", "Passport"),
            ("national_id", "National ID"),
            ("driving_license", "Driving License"),
            ("other", "Other"),
        ],
        related="partner_id.id_type",
        string="ID Type",
    )

    id_number = fields.Char(
        string="ID Number",
        related="partner_id.id_number",
    )

    nationality = fields.Many2one(
        "res.country",
        related="partner_id.nationality",
        string="Nationality",
    )

    date_of_birth = fields.Date(
        related="partner_id.date_of_birth",
        string="Date of Birth",
    )

    gender = fields.Selection(
        [
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
        ],
        related="partner_id.gender",
        string="Gender",
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

    adult_count = fields.Integer(
        string="Adults",
        compute="_compute_statistics",
    )

    child_count = fields.Integer(
        string="Children",
        compute="_compute_statistics",
    )

    infant_count = fields.Integer(
        string="Infant",
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

    room_discount_amount = fields.Monetary(
        compute="_compute_amounts",
        string="Room Discount",
        store=True,
        currency_field="currency_id",
    )


    service_discount_amount = fields.Monetary(
        compute="_compute_amounts",
        string="Service Discount",
        store=True,
        currency_field="currency_id",
    )


    discount_amount = fields.Monetary(
        compute="_compute_amounts",
        string="Total Discount",
        store=True,
        currency_field="currency_id",
    )

    tax_amount = fields.Monetary(
        compute="_compute_amounts",
        string="Total Tax",
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

    service_tax_amount = fields.Monetary(
        string="Service Tax",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )

    room_tax_amount = fields.Monetary(
        string="Room Tax",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )

    total_amount = fields.Monetary(
        compute="_compute_amounts",
        string="Total",
        store=True,
        currency_field="currency_id",
    )

    booking_date = fields.Datetime(
        string="Booking Date",
        default=fields.Datetime.now,
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
        help="Expected arrival time.",
    )

    departure_time = fields.Float(
        string="Expected Departure",
        help="Expected departure time.",
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

    room_booking_ids = fields.One2many(
        "hotel.room.booking",
        "reservation_id",
        string="Room Bookings",
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
        "product.product",
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
    room_booking_count = fields.Integer(string="Room Bookings", compute="_compute_statistics", )
    room_count = fields.Integer(string="Rooms", compute="_compute_statistics", )

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

    internal_notes = fields.Text(
        string="Guest Notes",
    )

    guest_notes = fields.Text(
        string="Internal Notes",
    )

    folio_ids = fields.One2many(
        "hotel.guest.folio",
        "reservation_id",
        string="Guest Folios",
    )

    folio_count = fields.Integer(
        string="Folio Count",
        compute="_compute_folio_balance",
    )

    folio_balance = fields.Monetary(
        string="Folio Balance",
        compute="_compute_folio_balance",
        currency_field="currency_id",
    )

    def _compute_folio_balance(self):
        for reservation in self:
            folios = reservation.folio_ids
            reservation.folio_count = len(folios)
            reservation.folio_balance = sum(
                folios.mapped("balance_amount")
            )

    # ---------------------------------------------------------
    # Compute
    # ---------------------------------------------------------

    @api.onchange("check_in", "check_out")
    def _onchange_stay_dates(self):
        for record in self:
            for line in record.line_ids:
                if record.check_in:
                    line.check_in = record.check_in
                if record.check_out:
                    line.check_out = record.check_out

    @api.onchange("hotel_id")
    def _onchange_hotel_id(self):
        for record in self:
            for line in record.line_ids:
                if record.hotel_id:
                    line.hotel_id = record.hotel_id

    @api.depends("check_in", "check_out")
    def _compute_nights(self):
        for record in self:
            record.night_count = 0

            if record.check_in and record.check_out:
                delta = record.check_out.date() - record.check_in.date()
                record.night_count = max(delta.days, 1)

    @api.depends("line_ids", "line_ids.room_amount", "line_ids.service_amount", "line_ids.service_tax_amount", "line_ids.discount_amount","line_ids.service_line_discounts","line_ids.total_discount_amount", "line_ids.tax_amount", "line_ids.subtotal", "line_ids.total")
    def _compute_amounts(self):
        for reservation in self:
            lines = reservation.line_ids
            reservation.room_amount = sum(lines.mapped("room_amount"))
            reservation.service_amount = sum(lines.mapped("service_amount"))
            reservation.room_discount_amount = sum(lines.mapped("discount_amount"))
            reservation.service_discount_amount = sum(lines.mapped("service_line_discounts"))
            reservation.discount_amount = sum(lines.mapped("total_discount_amount"))
            reservation.room_tax_amount = sum(lines.mapped("tax_amount"))
            reservation.service_tax_amount = sum(lines.mapped("service_tax_amount"))
            reservation.tax_amount = (sum(lines.mapped("tax_amount")) + sum(lines.mapped("service_tax_amount")))
            reservation.subtotal = sum(lines.mapped("subtotal"))
            reservation.total_amount = sum(lines.mapped("total"))

    @api.depends("line_ids", "line_ids.room_booking_id" ,"line_ids.room_id", "line_ids.adults", "line_ids.infants", "line_ids.children")
    def _compute_statistics(self):
        for reservation in self:
            lines = reservation.line_ids
            reservation.room_booking_count = len(lines.mapped("room_id"))
            reservation.room_count = len(lines.mapped("room_id"))
            reservation.adult_count = sum(lines.mapped("adults"))
            reservation.child_count = sum(lines.mapped("children"))
            reservation.infant_count = sum(lines.mapped("infants"))
            reservation.guest_count = (reservation.adult_count + reservation.child_count + reservation.infant_count)

    def action_open_room_bookings(self):
        self.ensure_one()

        booking_ids = self.line_ids.mapped("room_booking_id").ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Room Bookings"),
            "res_model": "hotel.room.booking",
            "view_mode": "list,form",
            "domain": [("id", "in", booking_ids), ],
            "context": {"default_reservation_id": self.id, },
        }

    def action_view_guest_folios(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Guest Folio"),
            "res_model": "hotel.guest.folio",
            "view_mode": "list,form",
            "domain": [
                ("reservation_id", "=", self.id),
            ],
            "context": {
                "default_partner_id": self.partner_id.id,
                "default_reservation_id": self.id,
            },
        }

    # ---------------------------------------------------------
    # Constraints
    # ---------------------------------------------------------

    @api.constrains("check_in", "check_out")
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

    @api.constrains("line_ids")
    def _check_reservation_lines(self):
        for reservation in self:
            if reservation.state in ("cancelled", "completed"):
                continue
            assigned_lines = reservation.line_ids.filtered(lambda l: l.room_id)
            for i, l1 in enumerate(assigned_lines):
                l1_in = l1.check_in or reservation.check_in
                l1_out = l1.check_out or reservation.check_out
                for l2 in assigned_lines[i + 1:]:
                    if l1.room_id.id == l2.room_id.id:
                        l2_in = l2.check_in or reservation.check_in
                        l2_out = l2.check_out or reservation.check_out
                        if l1_in and l1_out and l2_in and l2_out:
                            if l1_in < l2_out and l1_out > l2_in:
                                raise ValidationError(
                                    _(
                                        "Room '%s' is assigned more than once for overlapping dates within this reservation."
                                    ) % l1.room_id.display_name
                                )

    @api.constrains("line_ids")
    def _check_adults(self):
        for record in self:
            if record.line_ids and record.adult_count <= 0:
                raise ValidationError(_("At least one adult is required."))

    # ---------------------------------------------------------
    # ORM
    # ---------------------------------------------------------

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        checkin_time = float(self.env["ir.config_parameter"].sudo().get_param("vs_hotel_management.checkin_time_default"))
        checkout_time = float(self.env["ir.config_parameter"].sudo().get_param("vs_hotel_management.checkout_time_default"))

        print("Checkin Time",checkin_time)
        print("Checkout Time",checkout_time)

        today = fields.Date.context_today(self)
        tomorrow = today + relativedelta(days=1)

        ci_hours = int(checkin_time)
        ci_minutes = int((checkin_time - ci_hours) * 60)
        co_hours = int(checkout_time)
        co_minutes = int((checkout_time - co_hours) * 60)

        if "check_in" in fields_list and not res.get("check_in"):
            res["check_in"] = datetime.datetime.combine(today, datetime.time(ci_hours, ci_minutes))
        if "check_out" in fields_list and not res.get("check_out"):
            res["check_out"] = datetime.datetime.combine(tomorrow, datetime.time(co_hours, co_minutes))

        return res

    # ---------------------------------------------------------
    # ORM
    # ---------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):

        sequence = self.env["ir.sequence"]

        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = (sequence.next_by_code("hotel.reservation") or "/")

        records = super().create(vals_list)

        for reservation in records:
            if reservation.state != "draft":
                reservation._validate_reservation()

        return records

    def write(self, vals):

        locked_states = (
            "reserved",
            "checked_in",
            "checked_out",
            "completed",
            "cancelled",
            "no_show",
        )

        protected_fields = {
            "hotel_id",
            "check_in",
            "check_out",
            "partner_id",
        }

        for reservation in self:

            # ---------------------------------------------------------
            # Reservation-level fields
            # ---------------------------------------------------------
            if (
                    protected_fields.intersection(vals.keys())
                    and reservation.state in locked_states
            ):
                raise UserError(
                    _(
                        "Operational reservations cannot be modified directly."
                    )
                )

        res = super().write(vals)

        date_or_lines_changed = any(k in vals for k in ("check_in", "check_out", "line_ids"))
        if date_or_lines_changed:
            for reservation in self:
                if reservation.state in ("confirmed", "reserved", "checked_in"):
                    reservation._validate_reservation()

        return res

    def unlink(self):

        for reservation in self:

            if reservation.state != "draft":
                raise UserError(_("Only draft reservations can be deleted."))

        return super().unlink()

    def _has_room_line_modification(self, commands):
        """
        Check whether line_ids commands modify the reservation's
        room lines.

        Service lines are NOT handled here because service_line_ids
        belongs to the reservation line.
        """

        for command in commands:

            if not command:
                continue

            operation = command[0]

            # CREATE
            if operation == Command.CREATE:
                return True

            # UPDATE
            if operation == Command.UPDATE:
                return True

            # DELETE
            if operation == Command.DELETE:
                return True

            # UNLINK
            if operation == Command.UNLINK:
                return True

            # CLEAR
            if operation == Command.CLEAR:
                return True

            # SET
            if operation == Command.SET:
                return True

        return False

    def _has_line_modification(self, commands):

        for command in commands:

            if not command:
                continue

            operation = command[0]

            if operation in (Command.CREATE, Command.UPDATE, Command.DELETE, Command.UNLINK, Command.CLEAR, Command.SET):
                return True

        return False

    # =========================================================
    # WORKFLOW
    # =========================================================

    def action_confirm(self):
        """
        Confirm the reservation.

        Confirmation validates the reservation but does not
        occupy or reserve physical rooms yet.
        """

        for reservation in self:

            if reservation.state != "draft":
                raise UserError(_("Only draft reservations can be confirmed."))

            if not reservation.line_ids:
                raise ValidationError(_("A reservation must contain at least one room before it can be confirmed."))

            # Lock room rows to prevent concurrent booking race conditions
            room_ids = reservation.line_ids.mapped("room_id").ids
            if room_ids:
                self.env.cr.execute(
                    "SELECT id FROM hotel_room WHERE id IN %s FOR UPDATE",
                    (tuple(room_ids),)
                )

            reservation._validate_reservation()

            for line in reservation.line_ids:
                if not line.room_id:
                    raise ValidationError(
                        _("Each reservation line must have a room.")
                    )

                booking = line._create_room_booking()

            reservation.state = "confirmed"

        return True

    # =========================================================
    # RESERVE
    # =========================================================

    def action_reserve(self):
        """
        Reserve all rooms belonging to the reservation.

        Each reservation line creates its own room booking.
        """

        for reservation in self:

            if reservation.state not in ("confirmed", "draft"):
                raise UserError(_("Only draft or confirmed reservations can be reserved."))

            if not reservation.line_ids:
                raise UserError(_("At least one reservation line is required before reserving the reservation."))

            # Lock room rows to prevent concurrent booking race conditions
            room_ids = reservation.line_ids.mapped("room_id").ids
            if room_ids:
                self.env.cr.execute(
                    "SELECT id FROM hotel_room WHERE id IN %s FOR UPDATE",
                    (tuple(room_ids),)
                )

            reservation._validate_reservation()

            created_bookings = self.env["hotel.room.booking"]

            for line in reservation.line_ids:
                booking = line._create_room_booking()

                created_bookings |= booking

                line.room_id.write({
                    "status": "reserved",
                })

            reservation.state = "reserved"

    # =========================================================
    # CHECK IN
    # =========================================================

    def action_check_in(self):
        """
        Check in all reserved room bookings belonging
        to the reservation and create/open the guest folio.
        """

        for reservation in self:

            if reservation.state != "reserved":
                raise UserError(
                    _(
                        "Only reserved reservations can be checked in."
                    )
                )

            # Lock room rows to prevent concurrent booking race conditions
            room_ids = reservation.line_ids.mapped("room_id").ids
            if room_ids:
                self.env.cr.execute(
                    "SELECT id FROM hotel_room WHERE id IN %s FOR UPDATE",
                    (tuple(room_ids),)
                )

            # Final availability and operational status consistency check before check-in (Section 13)
            reservation._validate_reservation(for_check_in=True)

            bookings = reservation.line_ids.mapped(
                "room_booking_id"
            ).filtered(
                lambda booking: booking.state == "reserved"
            )

            if not bookings:
                raise UserError(
                    _("There are no reserved room bookings to check in.")
                )

            # -------------------------------------------------
            # 1. Check in room bookings
            # -------------------------------------------------
            bookings.action_check_in()

            # -------------------------------------------------
            # 2. Create / open guest folio
            # -------------------------------------------------
            reservation._create_guest_folio()

            # -------------------------------------------------
            # 3. Update reservation state
            # -------------------------------------------------
            reservation.state = "checked_in"

        return True

    def _create_guest_folio(self):
        Folio = self.env["hotel.guest.folio"]
        folios = self.env["hotel.guest.folio"]

        for reservation in self:

            if not reservation.partner_id:
                raise UserError(
                    _(
                        "A guest must be selected before checking in "
                        "reservation %s."
                    )
                    % reservation.display_name
                )

            # -------------------------------------------------
            # Find existing folio
            # -------------------------------------------------
            folio = Folio.search(
                [
                    ("reservation_id", "=", reservation.id),
                    ("state", "!=", "cancelled"),
                ],
                limit=1,
            )

            # -------------------------------------------------
            # Create folio if it does not exist
            # -------------------------------------------------
            if not folio:
                folio = Folio.create(
                    {
                        "partner_id": reservation.partner_id.id,
                        "reservation_id": reservation.id,
                        "check_in": reservation.check_in,
                        "check_out": reservation.check_out,
                        "hotel_id": reservation.hotel_id.id,
                        "company_id": reservation.company_id.id,
                        "state": "draft",
                    }
                )

            # -------------------------------------------------
            # Open folio
            # -------------------------------------------------
            if folio.state == "draft":
                folio.action_open()

            # -------------------------------------------------
            # Generate room charges
            # -------------------------------------------------
            reservation._create_folio_room_charges(folio)

            folios |= folio

        return folios

    def _create_folio_room_charges(self, folio):
        FolioLine = self.env["hotel.guest.folio.line"]

        for reservation in self:
            for line in reservation.line_ids:

                if not line.room_id:
                    continue

                # Prevent duplicate room charges
                existing_line = FolioLine.search(
                    [
                        ("folio_id", "=", folio.id),
                        ("reservation_line_id", "=", line.id),
                        ("charge_type", "=", "room"),
                    ],
                    limit=1,
                )

                if existing_line:
                    continue

                # Number of nights
                quantity = line.night_count or 1.0

                # Room amount is already calculated on reservation line
                unit_price = (
                    line.room_amount / quantity
                    if quantity
                    else line.room_amount
                )

                # Convert discount amount into percentage
                discount = 0.0
                if line.room_amount:
                    discount = (
                                       line.discount_amount / line.room_amount
                               ) * 100.0

                folio.add_charge(
                    description=_("Room %s") % line.room_id.display_name,
                    charge_type="room",
                    product=line.product_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    discount=discount,
                    tax_ids=line.tax_ids,
                    reservation_line=line,
                    room_booking=line.room_booking_id,
                )

    def _create_folio_service_charges(self, folio):
        self.ensure_one()

        for reservation_line in self.line_ids:
            for service_line in reservation_line.service_line_ids:

                existing_line = self.env[
                    "hotel.guest.folio.line"
                ].search(
                    [
                        ("folio_id", "=", folio.id),
                        (
                            "reservation_service_line_id",
                            "=",
                            service_line.id,
                        ),
                    ],
                    limit=1,
                )

                if existing_line:
                    continue

                product = service_line.product_id

                if not product:
                    continue

                gross_amount = (
                        service_line.quantity
                        * service_line.price_unit
                )

                discount_percentage = 0.0

                if gross_amount:
                    discount_percentage = (
                                                  service_line.discount_amount
                                                  / gross_amount
                                          ) * 100.0

                folio.add_charge(
                    description=product.display_name,
                    charge_type="service",
                    product=product,
                    quantity=service_line.quantity,
                    unit_price=service_line.price_unit,
                    discount=discount_percentage,
                    tax_ids=service_line.tax_ids,
                    reservation_line=reservation_line,
                    reservation_service_line=service_line,
                    room_booking=(
                        reservation_line.room_booking_id
                    ),
                )
    # =========================================================
    # CHECK OUT
    # =========================================================

    def action_check_out(self):
        """
        Check out all rooms belonging to the reservation.
        """

        for reservation in self:

            if reservation.state != "checked_in":
                raise UserError(
                    _(
                        "Only checked-in reservations "
                        "can be checked out."
                    )
                )

            bookings = reservation.line_ids.mapped("room_booking_id").filtered(lambda booking: booking.state == "checked_in")

            if not bookings:
                raise UserError(_("There are no checked-in rooms to check out."))

            bookings.action_check_out()

            folio = reservation.folio_ids.filtered(
                lambda f: f.state in ("open", "partially_paid")
            )[:1]

            if folio:
                reservation._create_folio_service_charges(folio)

            reservation.state = "checked_out"

        return True

    # =========================================================
    # COMPLETE
    # =========================================================

    def action_complete(self):
        """
        Mark the reservation as completed after checkout.
        """

        for reservation in self:

            if reservation.state != "checked_out":
                raise UserError(
                    _(
                        "Only checked-out reservations "
                        "can be completed."
                    )
                )

            bookings = reservation.line_ids.mapped("room_booking_id").filtered(
                lambda booking: booking.state == "checked_out")

            if not bookings:
                raise UserError(_("There are no checked-out rooms to complete."))

            bookings.action_complete()

            reservation.state = "completed"

    # =========================================================
    # CANCEL
    # =========================================================

    def action_cancel(self):
        """
        Cancel a reservation and release its reserved rooms.
        """

        for reservation in self:

            reservation._check_reservation_manager()

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
                line._cancel_room_booking()

                line.room_id.write({
                    "status": "available"
                })

            reservation.state = "cancelled"

    # =========================================================
    # NO SHOW
    # =========================================================

    def action_no_show(self):
        for reservation in self:

            if reservation.state not in (
                    "confirmed",
                    "reserved",
            ):
                raise UserError(
                    _(
                        "Only confirmed or reserved reservations "
                        "can be marked as No Show."
                    )
                )

            reservation.line_ids.mapped(
                "room_booking_id"
            ).action_release()

            reservation.state = "no_show"

        return True

    # =========================================================
    # RESET TO DRAFT
    # =========================================================

    def action_reset_to_draft(self):
        for reservation in self:

            if reservation.state not in (
                    "confirmed",
                    "cancelled",
            ):
                raise UserError(
                    _(
                        "This reservation cannot be reset to draft "
                        "from its current state."
                    )
                )

            # Reset related cancelled room bookings.
            cancelled_bookings = reservation.room_booking_ids.filtered(
                lambda booking: booking.state == "cancelled"
            )

            cancelled_bookings.write({
                "state": "reserved",
            })

            reservation.state = "draft"

    # =========================================================
    # VALIDATION
    # =========================================================

    def _validate_reservation(self, for_check_in=False):
        """
        Validate the reservation and all its lines before
        confirmation/reservation/check-in.
        """

        self.ensure_one()

        if not self.partner_id:
            raise ValidationError(
                _("A guest is required.")
            )

        if not self.hotel_id:
            raise ValidationError(
                _("A hotel is required.")
            )

        if not self.check_in:
            raise ValidationError(
                _("Check-in is required.")
            )

        if not self.check_out:
            raise ValidationError(
                _("Check-out is required.")
            )

        if self.check_out <= self.check_in:
            raise ValidationError(
                _(
                    "Check-out must be later than check-in."
                )
            )

        req_id = (
            self.hotel_id.require_guest_identification
            or self.env["ir.config_parameter"].sudo().get_param("vs_hotel_management.require_guest_id")
        )
        if req_id and not self.partner_id.id_number:
            raise ValidationError(
                _("Guest identification (ID Number) is required for reservations at %s.")
                % self.hotel_id.name
            )

        if not self.line_ids:
            raise ValidationError(
                _(
                    "At least one reservation line is required."
                )
            )

        self._check_duplicate_rooms()

        allow_overbooking = False
        if self.hotel_id:
            allow_overbooking = self.hotel_id.allow_overbooking
        if not allow_overbooking:
            param = self.env["ir.config_parameter"].sudo().get_param(
                "vs_hotel_management.allow_overbooking", default="False"
            )
            allow_overbooking = param in (True, "True", "1")

        for line in self.line_ids:
            line._validate_reservation_line(for_check_in=for_check_in, allow_overbooking=allow_overbooking)

    # =========================================================
    # ACTIONS / EMAILS
    # =========================================================

    def action_send_reservation_email(self):
        """Open email composer with reservation confirmation template."""
        self.ensure_one()
        template = self.env.ref(
            "vs_hotel_management.mail_template_hotel_reservation_confirmation",
            raise_if_not_found=False,
        )
        compose_form = self.env.ref(
            "mail.email_compose_message_wizard_form",
            raise_if_not_found=False,
        )
        ctx = {
            "default_model": "hotel.reservation",
            "default_res_ids": self.ids,
            "default_use_template": bool(template),
            "default_template_id": template.id if template else False,
            "default_composition_mode": "comment",
            "mark_so_as_sent": True,
            "force_email": True,
        }
        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "views": [(compose_form.id if compose_form else False, "form")],
            "view_id": compose_form.id if compose_form else False,
            "target": "new",
            "context": ctx,
        }

    # =========================================================
    # SECURITY
    # =========================================================

    def _check_reservation_manager(self):
        if self.env.is_superuser():
            return
        if not self.env.user.has_group(
                "vs_hotel_management.group_hotel_room_manager"
        ):
            raise AccessError(
                _(
                    "Only a hotel manager can perform "
                    "this operation."
                )
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

    _sql_constraints = [
        (
            "hotel_reservation_name_unique",
            "unique(name, company_id)",
            "Reservation reference must be unique.",
        ),
    ]
