from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_hotel_guest = fields.Boolean(
        string="Hotel Guest",
        help="Enable this option when the contact is a hotel guest.",
    )

    guest_code = fields.Char(
        string="Guest Code",
        readonly=True,
        copy=False,
        index=True,
    )

    id_type = fields.Selection(
        [
            ("passport", "Passport"),
            ("national_id", "National ID"),
            ("driving_license", "Driving License"),
            ("other", "Other"),
        ],
        string="ID Type",
    )

    id_number = fields.Char(
        string="ID Number",
    )

    nationality = fields.Many2one(
        "res.country",
        string="Nationality",
    )

    date_of_birth = fields.Date(
        string="Date of Birth",
    )

    gender = fields.Selection(
        [
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
        ],
        string="Gender",
    )

    hotel_guest_notes = fields.Text(
        string="Guest Notes",
    )

    reservation_count = fields.Integer(
        string="Reservations",
        compute="_compute_hotel_guest_statistics",
    )

    room_booking_count = fields.Integer(
        string="Room Bookings",
        compute="_compute_hotel_guest_statistics",
    )

    folio_count = fields.Integer(
        string="Guest Folios",
        compute="_compute_hotel_guest_statistics",
    )

    hotel_invoice_count = fields.Integer(
        string="Guest Invoices",
        compute="_compute_hotel_guest_statistics",
    )

    whatsapp_log_count = fields.Integer(
        string="WhatsApp Messages",
        compute="_compute_hotel_guest_statistics",
    )

    def _compute_hotel_guest_statistics(self):
        Reservation = self.env["hotel.reservation"]
        RoomBooking = self.env["hotel.room.booking"]
        Folio = self.env["hotel.guest.folio"]
        AccountMove = self.env["account.move"]
        WhatsappLog = self.env["hotel.whatsapp.log"]

        for partner in self:
            partner.reservation_count = Reservation.search_count([
                ("partner_id", "=", partner.id),
            ])

            partner.room_booking_count = RoomBooking.search_count([
                ("guest_id", "=", partner.id),
            ])

            partner.folio_count = Folio.search_count([
                ("partner_id", "=", partner.id),
            ])

            partner.hotel_invoice_count = AccountMove.search_count([
                ("partner_id", "=", partner.id),
                ("move_type", "in", ("out_invoice", "out_refund")),
            ])

            partner.whatsapp_log_count = WhatsappLog.search_count([
                ("recipient_id", "=", partner.id),
            ])

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for partner in records:
            partner._generate_guest_code()

        return records

    def write(self, vals):
        result = super().write(vals)

        if vals.get("is_hotel_guest"):
            for partner in self:
                partner._generate_guest_code()

        return result

    def _generate_guest_code(self):
        self.ensure_one()

        if self.is_hotel_guest and not self.guest_code:
            self.guest_code = (
                self.env["ir.sequence"].next_by_code("hotel.guest")
                or "/"
            )

    def action_view_hotel_reservations(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Guest Reservations",
            "res_model": "hotel.reservation",
            "view_mode": "list,form",
            "domain": [
                ("partner_id", "=", self.id),
            ],
            "context": {
                "default_partner_id": self.id,
            },
        }

    def action_view_hotel_room_bookings(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Guest Room Bookings",
            "res_model": "hotel.room.booking",
            "view_mode": "list,form",
            "domain": [
                ("guest_id", "=", self.id),
            ],
            "context": {
                "default_guest_id": self.id,
            },
        }

    def action_view_hotel_folios(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Guest Folios"),
            "res_model": "hotel.guest.folio",
            "view_mode": "list,form",
            "domain": [
                ("partner_id", "=", self.id),
            ],
            "context": {
                "default_partner_id": self.id,
            },
        }

    def action_view_hotel_invoices(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [
                ("partner_id", "=", self.id),
                ("move_type", "in", ("out_invoice", "out_refund")),
            ],
            "context": {
                "default_partner_id": self.id,
                "default_move_type": "out_invoice",
            },
        }

    def action_view_whatsapp_logs(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("WhatsApp Messages"),
            "res_model": "hotel.whatsapp.log",
            "view_mode": "list,form",
            "domain": [
                ("recipient_id", "=", self.id),
            ],
            "context": {
                "default_recipient_id": self.id,
            },
        }