from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HotelRoomBooking(models.Model):
    _name = "hotel.room.booking"
    _description = "Hotel Room Booking"
    _order = "check_in, room_id"
    _rec_name = "room_id"
    _check_company_auto = True

    reservation_id = fields.Many2one(
        "hotel.reservation",
        string="Reservation",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )

    reservation_line_id = fields.Many2one(
        "hotel.reservation.line",
        string="Reservation Line",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )

    room_id = fields.Many2one(
        "hotel.room",
        string="Room",
        required=True,
        ondelete="restrict",
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
        check_company=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="reservation_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    check_in = fields.Datetime(
        string="Check In",
        required=True,
        index=True,
    )

    check_out = fields.Datetime(
        string="Check Out",
        required=True,
        index=True,
    )

    state = fields.Selection(
        [
            ("reserved", "Reserved"),
            ("checked_in", "Checked In"),
            ("checked_out", "Checked Out"),
            ("released", "Released"),
        ],
        string="Status",
        default="reserved",
        required=True,
        index=True,
    )

    active = fields.Boolean(
        default=True,
        index=True,
    )

    duration = fields.Float(
        string="Duration",
        compute="_compute_duration",
    )

    @api.depends("check_in", "check_out")
    def _compute_duration(self):
        for record in self:
            if record.check_in and record.check_out:
                delta = record.check_out - record.check_in
                record.duration = delta.total_seconds() / 3600.0
            else:
                record.duration = 0.0

    @api.constrains(
        "check_in",
        "check_out",
    )
    def _check_dates(self):
        for record in self:
            if record.check_in >= record.check_out:
                raise ValidationError(
                    _(
                        "Check-out must be later than check-in."
                    )
                )

    @api.constrains(
        "reservation_id",
        "reservation_line_id",
    )
    def _check_reservation_consistency(self):
        for record in self:

            if (
                record.reservation_line_id.reservation_id
                != record.reservation_id
            ):
                raise ValidationError(
                    _(
                        "The reservation line does not belong "
                        "to the selected reservation."
                    )
                )

    @api.constrains("room_id", "hotel_id")
    def _check_room_hotel(self):
        for record in self:

            if (
                record.room_id
                and record.hotel_id
                and record.room_id.hotel_id != record.hotel_id
            ):
                raise ValidationError(
                    _(
                        "The selected room does not belong "
                        "to the selected hotel."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for record in records:
            record._validate_booking()

        return records

    def _validate_booking(self):
        """Validate the booking before it becomes an inventory lock."""

        self.ensure_one()

        if not self.room_id:
            raise ValidationError(
                _("A room is required.")
            )

        if not self.reservation_id:
            raise ValidationError(
                _("A reservation is required.")
            )

        if self.reservation_id.state not in (
            "reserved",
            "checked_in",
        ):
            raise ValidationError(
                _(
                    "A room booking can only exist for a "
                    "reserved or checked-in reservation."
                )
            )

        if self.state == "released":
            return

        if self.room_id.status == "out_of_order":
            raise ValidationError(
                _(
                    "Room '%s' is out of order."
                ) % self.room_id.display_name
            )

        if self.room_id.status == "maintenance":
            raise ValidationError(
                _(
                    "Room '%s' is under maintenance."
                ) % self.room_id.display_name
            )

    def action_check_in(self):
        for booking in self:
            if booking.state != "reserved":
                continue

            booking.write({
                "state": "checked_in",
            })

    def action_check_out(self):
        for booking in self:
            if booking.state != "checked_in":
                continue

            booking.write({
                "state": "checked_out",
            })

    def action_release(self):
        for booking in self:
            if booking.state == "released":
                continue

            booking.write({
                "state": "released",
                "active": False,
            })