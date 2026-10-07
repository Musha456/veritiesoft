from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class HotelRoomBooking(models.Model):
    _name = "hotel.room.booking"
    _description = "Hotel Room Booking"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "check_in, room_id"
    _check_company_auto = True

    name = fields.Char(
        string="Booking Reference",
        readonly=True,
        copy=False,
        default="/",
        tracking=True,
        index=True,
    )

    reservation_id = fields.Many2one(
        "hotel.reservation",
        string="Reservation",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
        check_company=True,
    )

    reservation_line_id = fields.Many2one(
        "hotel.reservation.line",
        string="Reservation Line",
        ondelete="cascade",
        index=True,
        check_company=True,
    )

    hotel_id = fields.Many2one(
        "hotel.hotel",
        string="Hotel",
        related="reservation_id.hotel_id",
        store=True,
        readonly=True,
        index=True,
    )

    room_id = fields.Many2one(
        "hotel.room",
        string="Room",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        check_company=True,
    )

    room_category_id = fields.Many2one(
        "hotel.room.category",
        string="Room Category",
        related="room_id.room_category_id",
        store=True,
        readonly=True,
    )

    check_in = fields.Datetime(
        string="Check In",
        required=True,
        tracking=True,
        index=True,
    )

    check_out = fields.Datetime(
        string="Check Out",
        required=True,
        tracking=True,
        index=True,
    )

    adult_count = fields.Integer(
        related="reservation_line_id.adults",
        string="Adults",
        store=True,
        readonly=True,
    )

    child_count = fields.Integer(
        related="reservation_line_id.children",
        string="Children",
        store=True,
        readonly=True,
    )

    guest_count = fields.Integer(
        compute="_compute_guest_count",
        store=True,
    )



    state = fields.Selection(
        [
            ("reserved", "Reserved"),
            ("checked_in", "Checked In"),
            ("checked_out", "Checked Out"),
            ("released", "Released"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="reserved",
        required=True,
        tracking=True,
        index=True,
    )

    guest_id = fields.Many2one(
        "res.partner",
        string="Guest",
        related="reservation_id.partner_id",
        store=True,
        readonly=True,
        index=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="reservation_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    currency_id = fields.Many2one(
        related="reservation_id.currency_id",
        store=True,
        readonly=True,
    )

    active = fields.Boolean(
        default=True,
        tracking=True,
    )

    duration = fields.Float(
        string="Duration",
        compute="_compute_duration",
    )

    night_count = fields.Integer(
        string="Nights",
        compute="_compute_night_count",
        store=True,
    )



    @api.depends("check_in", "check_out")
    def _compute_duration(self):
        for booking in self:
            if booking.check_in and booking.check_out:
                delta = booking.check_out - booking.check_in
                booking.duration = delta.total_seconds() / 3600
            else:
                booking.duration = 0.0

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):

        for vals in vals_list:

            if vals.get("name", "/") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "hotel.room.booking"
                    )
                    or "/"
                )

        room_ids = [vals["room_id"] for vals in vals_list if vals.get("room_id")]
        if room_ids:
            self.env.cr.execute(
                "SELECT id FROM hotel_room WHERE id IN %s FOR UPDATE",
                (tuple(room_ids),)
            )

        bookings = super().create(vals_list)

        for booking in bookings:
            booking._validate_dates()
            booking._validate_room_availability()

        return bookings

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    def _validate_dates(self):

        for booking in self:

            if booking.check_out <= booking.check_in:
                raise ValidationError(
                    _(
                        "Check-out must be later than check-in."
                    )
                )

    def _validate_room_availability(self):

        for booking in self:

            if booking.state not in (
                "reserved",
                "checked_in",
            ):
                continue

            overlapping_booking = self.search(
                [
                    ("id", "!=", booking.id),
                    ("room_id", "=", booking.room_id.id),
                    ("state", "in", (
                        "reserved",
                        "checked_in",
                    )),
                    ("check_in", "<", booking.check_out),
                    ("check_out", ">", booking.check_in),
                ],
                limit=1,
            )

            if overlapping_booking:
                raise ValidationError(
                    _(
                        "Room %(room)s is already booked "
                        "from %(check_in)s to %(check_out)s."
                    )
                    % {
                        "room": booking.room_id.display_name,
                        "check_in": overlapping_booking.check_in,
                        "check_out": overlapping_booking.check_out,
                    }
                )

    # ---------------------------------------------------------
    # RESERVE
    # ---------------------------------------------------------

    def action_confirm(self):

        for booking in self:

            if booking.state != "reserved":
                raise UserError(
                    _(
                        "Only reserved room bookings can be confirmed."
                    )
                )

            booking._validate_dates()
            booking._validate_room_availability()

    # ---------------------------------------------------------
    # CHECK IN
    # ---------------------------------------------------------

    def action_check_in(self):

        for booking in self:
            if booking.state != "reserved":
                raise UserError(_("Only reserved room bookings can be checked in."))

            if not booking.room_id:
                raise UserError(_("A room is required before check-in."))

            if booking.room_id.status in ("maintenance", "out_of_order"):
                raise ValidationError(
                    _("Room '%s' cannot be checked in because it is currently unavailable due to %s.")
                    % (booking.room_id.display_name, booking.room_id.status.replace("_", " "))
                )

            if booking.room_id.status in ("cleaning", "dirty"):
                raise ValidationError(
                    _("Room '%s' is not ready for check-in (status: %s).")
                    % (booking.room_id.display_name, booking.room_id.status.title())
                )

            booking.write({"state":"checked_in"})
            booking.room_id.write({"status":"occupied"})

            if booking.reservation_id:
                if booking.reservation_id.state != "checked_in":
                    booking.reservation_id.write({"state":"checked_in"})

        return True


    # ---------------------------------------------------------
    # CHECK OUT
    # ---------------------------------------------------------

    def action_check_out(self):

        for booking in self:

            if booking.state != "checked_in":
                raise UserError(_("Only checked-in room bookings can be checked out."))

            booking.write({"state":"checked_out"})

            mark_room_dirty_on_checkout = self.env['ir.config_parameter'].sudo().get_param('vs_hotel_management.mark_room_dirty_on_checkout')

            print("Mark room dirty on checkout",mark_room_dirty_on_checkout)

            if mark_room_dirty_on_checkout:
                booking.room_id.write({"status":"dirty"})
            else:
                booking.room_id.write({"status": "available"})

            if booking.reservation_id:

                self.env["hotel.housekeeping"].create_checkout_task(
                    room=booking.room_id,
                    reservation=booking.reservation_id,
                    room_booking=booking,
                )

                reservation = booking.reservation_id

                active_bookings = reservation.line_ids.mapped("room_booking_id").filtered(lambda b: b.state == "checked_in")

                if not active_bookings:
                    reservation.write({"state":"checked_out"})

        return True

    def action_complete(self):

        for booking in self:

            if booking.state != "checked_out":
                raise UserError(_("Only checked-out room bookings can be complete."))

            booking.write({"state":"completed"})

        return True

    # ---------------------------------------------------------
    # RELEASE
    # ---------------------------------------------------------

    def action_release(self):
        for booking in self:

            if booking.state in ("released", "cancelled"):
                continue

            reservation = booking.reservation_id

            if reservation and reservation.state in (
                    "checked_in",
                    "checked_out",
                    "completed",
            ):
                raise UserError(
                    _(
                        "Room booking %s cannot be released because "
                        "the current reservation has already started or completed the stay."
                    ) % booking.display_name
                )

            booking.write({
                "state": "released",
            })

        return True



    # ---------------------------------------------------------
    # CANCEL
    # ---------------------------------------------------------

    def action_cancel(self):
        for reservation in self:

            if reservation.state in (
                    "checked_in",
                    "checked_out",
                    "completed",
            ):
                raise UserError(
                    _(
                        "Reservation %s cannot be cancelled after "
                        "the stay has started."
                    ) % reservation.display_name
                )

            if reservation.state == "cancelled":
                continue

            # Release associated room bookings.
            reservation.reservation_line_id.mapped(
                "room_booking_id"
            ).action_release()

            reservation.state = "cancelled"

        return True

    # ---------------------------------------------------------
    # DELETE PROTECTION
    # ---------------------------------------------------------

    def unlink(self):

        raise UserError(
            _(
                "Room bookings cannot be deleted. "
                "Release or cancel the booking instead."
            )
        )

    def _set_room_reserved(self):
        self.ensure_one()

        room = self.room_id

        if room.status in (
                "maintenance",
                "out_of_order",
        ):
            raise ValidationError(
                _(
                    "Room '%s' cannot be reserved because "
                    "it is currently unavailable."
                )
                % room.display_name
            )

        if room.status == "available":
            room.status = "reserved"

    def _set_room_occupied(self):
        self.ensure_one()

        room = self.room_id

        if room.status in (
                "maintenance",
                "out_of_order",
        ):
            raise ValidationError(
                _(
                    "Room '%s' cannot be checked in because "
                    "it is unavailable."
                )
                % room.display_name
            )

        room.status = "occupied"

    def _set_room_dirty(self):
        self.ensure_one()

        if self.room_id:
            self.room_id.status = "dirty"

    @api.constrains(
        "room_id",
        "check_in",
        "check_out",
        "state",
    )
    def _check_room_booking_overlap(self):
        for booking in self:

            if not booking.room_id:
                continue

            if not booking.check_in or not booking.check_out:
                continue

            if booking.state not in ("reserved", "checked_in"):
                continue

            overlapping_booking = self.search(
                [
                    ("id", "!=", booking.id),
                    ("room_id", "=", booking.room_id.id),
                    ("state", "in", ("reserved", "checked_in")),
                    ("check_in", "<", booking.check_out),
                    ("check_out", ">", booking.check_in),
                ],
                limit=1,
            )

            if overlapping_booking:
                raise ValidationError(
                    _(
                        "Room %(room)s is already booked from "
                        "%(start)s to %(end)s.\n\n"
                        "Existing booking: %(booking)s"
                    )
                    % {
                        "room": booking.room_id.display_name,
                        "start": overlapping_booking.check_in,
                        "end": overlapping_booking.check_out,
                        "booking": overlapping_booking.display_name,
                    }
                )

    @api.depends("adult_count", "child_count")
    def _compute_guest_count(self):
        for booking in self:
            booking.guest_count = (
                    booking.adult_count
                    + booking.child_count
            )

    @api.depends("check_in", "check_out")
    def _compute_night_count(self):
        for booking in self:
            if booking.check_in and booking.check_out:
                booking.night_count = max(
                    0,
                    (booking.check_out - booking.check_in).days,
                )
            else:
                booking.night_count = 0

    @api.constrains(
        "check_in",
        "check_out",
    )
    def _check_dates(self):
        for booking in self:
            if booking.check_out <= booking.check_in:
                raise ValidationError(
                    _(
                        "Check-out must be later than check-in."
                    )
                )

    @api.constrains(
        "reservation_id",
        "reservation_line_id",
        "room_id",
        "check_in",
        "check_out",
    )
    def _check_reservation_consistency(self):
        for booking in self:

            line = booking.reservation_line_id

            if line.reservation_id != booking.reservation_id:
                raise ValidationError(
                    _(
                        "The reservation line does not belong "
                        "to the selected reservation."
                    )
                )

            if line.room_id != booking.room_id:
                raise ValidationError(
                    _(
                        "The booking room must match the "
                        "reservation line room."
                    )
                )

            if (
                    line.check_in != booking.check_in
                    or line.check_out != booking.check_out
            ):
                raise ValidationError(
                    _(
                        "Booking dates must match the "
                        "reservation line dates."
                    )
                )