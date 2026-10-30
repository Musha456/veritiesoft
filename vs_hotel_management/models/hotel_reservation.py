import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError, AccessError
from odoo import Command
import pytz
import logging

_logger = logging.getLogger(__name__)


class HotelReservation(models.Model):
    _name = "hotel.reservation"
    _description = "Hotel Reservation"
    _inherit = ["mail.thread", "mail.activity.mixin", "hotel.notification.mixin"]
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

    guest_phone = fields.Char(related="partner_id.phone", string="Guest Phone")

    guest_email = fields.Char(
        related="partner_id.email",
        string="Guest Email",
    )

    id_type = fields.Selection(
        # [
        #     ("passport", "Passport"),
        #     ("national_id", "National ID"),
        #     ("driving_license", "Driving License"),
        #     ("other", "Other"),
        # ],
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
        # [
        #     ("male", "Male"),
        #     ("female", "Female"),
        #     ("other", "Other"),
        # ],
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
        store=True,
        currency_field="currency_id",
    )

    room_amount = fields.Monetary(
        string="Room Amount",
        compute="_compute_amounts",
        store=True,
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

    untaxed_amount = fields.Monetary(
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
        help="Expected arrival time.",
    )

    departure_time = fields.Float(
        string="Expected Departure",
        help="Expected departure time.",
    )

    payment_status = fields.Selection(
        [
            ("unpaid", "Unpaid"),
            ("partially_paid", "Partially Paid"),
            ("paid", "Paid"),
        ],
        string="Payment Status",
        compute="_compute_payment_status",
        store=True,
        tracking=True,
    )

    folio_id = fields.Many2one(
        "hotel.guest.folio",
        string="Folio",
        compute="_compute_primary_folio",
        store=True,
    )

    booked_rooms_display = fields.Char(
        string="Booked Rooms",
        compute="_compute_booked_rooms_display",
        store=True,
    )

    agent_id = fields.Many2one(
        "res.partner",
        string="Travel Agent",
        domain="[('is_travel_agent', '=', True)]",
        tracking=True,
        help="Travel agent or agency associated with this booking.",
    )

    agent_commission_percentage = fields.Float(
        string="Agent Commission (%)",
        tracking=True,
        help="Commission percentage for the travel agent.",
    )

    agent_commission_amount = fields.Monetary(
        string="Commission Amount",
        compute="_compute_agent_commission",
        store=True,
        currency_field="currency_id",
        help="Total commission amount allocated to the travel agent calculated on room charges.",
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
    room_booking_count = fields.Integer(string="Room Booking Count", compute="_compute_statistics", )
    room_count = fields.Integer(string="Room Count", compute="_compute_statistics", )

    service_count = fields.Integer(
        compute="_compute_statistics",
    )

    payment_count = fields.Integer(
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

    invoice_amount = fields.Monetary(
        string="Folio Invoice",
        compute="_compute_folio_invoice",
        currency_field="currency_id",
    )

    whatsapp_log_count = fields.Integer(
        string="WhatsApp Logs",
        compute="_compute_whatsapp_log_count",
    )

    checkin_time_default = fields.Char(
        string="Default Check-in Time",
        compute="_compute_check_time_default",
    )

    checkout_time_default = fields.Char(
        string="Default Check-out Time",
        compute="_compute_check_time_default",
    )

    check_in_formatted = fields.Char(
        string="Check-In (Local Time)",
        compute="_compute_formatted_dates",
        help="Formatted check-in date and time in the hotel's business timezone.",
    )

    check_out_formatted = fields.Char(
        string="Check-Out (Local Time)",
        compute="_compute_formatted_dates",
        help="Formatted check-out date and time in the hotel's business timezone.",
    )

    @api.depends("check_in", "check_out", "hotel_id.timezone")
    def _compute_formatted_dates(self):
        for rec in self:
            rec.check_in_formatted = rec._format_datetime_local(rec.check_in) if rec.check_in else ""
            rec.check_out_formatted = rec._format_datetime_local(rec.check_out) if rec.check_out else ""

    @api.depends()
    def _compute_check_time_default(self):
        config = self.env["ir.config_parameter"].sudo()
        checkin_value = float(
            config.get_param(
                "vs_hotel_management.checkin_time_default",
                default="14.0",
            )
        )

        checkout_value = float(
            config.get_param(
                "vs_hotel_management.checkout_time_default",
                default="12.0",
            )
        )

        def fmt_time(val):
            total_minutes = round(val * 60)
            hours, minutes = divmod(total_minutes, 60)
            t = datetime.time(hours % 24, minutes % 60)
            return t.strftime("%I:%M %p").lstrip("0")

        checkin_formatted_time = fmt_time(checkin_value)
        checkout_formatted_time = fmt_time(checkout_value)

        for record in self:
            record.checkin_time_default = checkin_formatted_time
            record.checkout_time_default = checkout_formatted_time

    def _compute_folio_balance(self):
        for reservation in self:
            folios = reservation.folio_ids
            reservation.folio_count = len(folios)
            reservation.folio_balance = sum(
                folios.mapped("balance_amount")
            )

    def _compute_folio_invoice(self):
        for reservation in self:
            invoices = reservation.folio_ids.mapped("invoice_id").filtered(
                lambda invoice: invoice.move_type == "out_invoice"
            )
            reservation.invoice_amount = sum(
                invoices.mapped("amount_total")
            )

    @api.depends("folio_ids", "folio_ids.state")
    def _compute_primary_folio(self):
        for reservation in self:
            active_folios = reservation.folio_ids.filtered(lambda f: f.state != "cancelled")
            reservation.folio_id = active_folios[:1] if active_folios else self.env["hotel.guest.folio"]

    @api.depends("folio_ids", "folio_ids.state", "folio_ids.paid_amount", "folio_ids.balance_amount", "folio_ids.total_amount")
    def _compute_payment_status(self):
        for reservation in self:
            active_folios = reservation.folio_ids.filtered(lambda f: f.state != "cancelled")
            if not active_folios:
                reservation.payment_status = "unpaid"
                continue
            total = sum(active_folios.mapped("total_amount"))
            paid = sum(active_folios.mapped("paid_amount"))
            if any(f.state == "paid" for f in active_folios) or (total > 0 and paid >= total):
                reservation.payment_status = "paid"
            elif paid > 0 or any(f.state == "partially_paid" for f in active_folios):
                reservation.payment_status = "partially_paid"
            else:
                reservation.payment_status = "unpaid"

    @api.depends(
        "line_ids.room_id",
        "line_ids.room_id.room_number",
        "line_ids.room_category_id",
        "line_ids.room_category_id.name",
    )
    def _compute_booked_rooms_display(self):
        for reservation in self:
            rooms = []
            for line in reservation.line_ids:
                if line.room_id and line.room_id.room_number:
                    rooms.append(line.room_id.room_number)
                elif line.room_category_id and line.room_category_id.name:
                    rooms.append(line.room_category_id.name)
            reservation.booked_rooms_display = ", ".join(rooms) if rooms else "-"

    @api.onchange("agent_id")
    def _onchange_agent_id(self):
        if self.agent_id:
            if self.agent_id.agent_commission_percentage:
                self.agent_commission_percentage = self.agent_id.agent_commission_percentage
            else:
                ICP = self.env["ir.config_parameter"].sudo()
                self.agent_commission_percentage = float(
                    ICP.get_param("vs_hotel_management.default_agent_commission_percentage", 10.0) or 10.0
                )
        else:
            self.agent_commission_percentage = 0.0

    @api.depends("room_amount", "agent_commission_percentage", "agent_id")
    def _compute_agent_commission(self):
        for res in self:
            if res.agent_id and res.agent_commission_percentage:
                res.agent_commission_amount = (res.room_amount * res.agent_commission_percentage) / 100.0
            else:
                res.agent_commission_amount = 0.0

    def _get_stay_limits(self):
        """Return minimum and maximum stay limits from configuration settings."""
        self.ensure_one()

        config = self.env["ir.config_parameter"].sudo()

        minimum_stay = int(
            config.get_param(
                "vs_hotel_management.minimum_stay",
                default="1",
            )
        )

        maximum_stay = int(
            config.get_param(
                "vs_hotel_management.maximum_stay",
                default="365",
            )
        )

        if minimum_stay < 1 or maximum_stay < minimum_stay:
            raise ValidationError(
                _(
                    "Invalid stay configuration. The minimum stay "
                    "must be at least 1 night, and the maximum stay "
                    "must not be less than the minimum stay."
                )
            )

        return minimum_stay, maximum_stay

    # ---------------------------------------------------------
    # Onchange
    # ---------------------------------------------------------

    @api.onchange("check_in", "check_out")
    def _onchange_stay_dates(self):
        for record in self:
            for line in record.line_ids:
                if record.check_in:
                    line.check_in = record.check_in

                if record.check_out:
                    line.check_out = record.check_out

        # self._onchange_hotel_id()

    @api.onchange("hotel_id")
    def _onchange_hotel_id(self):
        config = self.env["ir.config_parameter"].sudo()

        checkin_time = float(
            config.get_param(
                "vs_hotel_management.checkin_time_default",
                default="14.0",
            )
        )
        checkout_time = float(
            config.get_param(
                "vs_hotel_management.checkout_time_default",
                default="12.0",
            )
        )

        for record in self:
            for line in record.line_ids:
                line.hotel_id = record.hotel_id

            hotel = record.hotel_id

            if not hotel:
                continue

            minimum_stay, maximum_stay = record._get_stay_limits()
            nights = record.night_count or minimum_stay

            if nights < minimum_stay or nights > maximum_stay:
                raise ValidationError(
                    _(
                        "The stay must be between %(minimum)s and "
                        "%(maximum)s night(s), according to the "
                        "configured stay limits."
                    ) % {
                        "minimum": minimum_stay,
                        "maximum": maximum_stay,
                    }
                )

            timezone_name = self.env.user.tz or (hotel and hotel.timezone) or self.env.company.partner_id.tz or "UTC"

            try:
                hotel_timezone = pytz.timezone(timezone_name)
            except pytz.UnknownTimeZoneError:
                hotel_timezone = pytz.UTC

            def to_time(value, label):
                if not 0 <= value < 24:
                    raise ValidationError(
                        _("%s must be between 00:00 and 23:59.") % label
                    )

                total_minutes = round(value * 60)

                if total_minutes >= 1440:
                    raise ValidationError(
                        _("%s must be earlier than 24:00.") % label
                    )

                hours, minutes = divmod(total_minutes, 60)
                return datetime.time(hours, minutes)

            def to_utc(local_date, local_time):
                local_datetime = datetime.datetime.combine(
                    local_date,
                    local_time,
                )

                try:
                    localized = hotel_timezone.localize(
                        local_datetime,
                        is_dst=None,
                    )
                except (
                        pytz.AmbiguousTimeError,
                        pytz.NonExistentTimeError,
                ):
                    raise ValidationError(
                        _(
                            "The configured time are ambiguous "
                            "or invalid in hotel timezone %s."
                        ) % timezone_name
                    )

                return localized.astimezone(
                    pytz.UTC
                ).replace(tzinfo=None)

            today = datetime.datetime.now(
                pytz.UTC
            ).astimezone(hotel_timezone).date()

            record.check_in = to_utc(
                today,
                to_time(
                    checkin_time,
                    _("Default Check-in Time"),
                ),
            )

            record.check_out = to_utc(
                today + relativedelta(days=nights),
                to_time(
                    checkout_time,
                    _("Default Check-out Time"),
                ),
            )

    @api.depends("check_in", "check_out")
    def _compute_nights(self):
        for record in self:
            record.night_count = 0

            if record.check_in and record.check_out:
                delta = record.check_out.date() - record.check_in.date()
                record.night_count = max(delta.days, 1)

    @api.depends("line_ids", "line_ids.room_amount", "line_ids.service_amount", "line_ids.service_tax_amount",
                 "line_ids.discount_amount", "line_ids.service_line_discounts", "line_ids.total_discount_amount",
                 "line_ids.tax_amount", "line_ids.subtotal", "line_ids.total")
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

    @api.depends(
        "line_ids",
        "line_ids.room_booking_id",
        "line_ids.room_id",
        "line_ids.adults",
        "line_ids.infants",
        "line_ids.children",
    )
    def _compute_statistics(self):
        for reservation in self:
            lines = reservation.line_ids

            reservation.room_booking_count = len(
                lines.mapped("room_booking_id")
            )
            reservation.room_count = len(
                lines.mapped("room_id")
            )

            reservation.adult_count = sum(lines.mapped("adults"))
            reservation.child_count = sum(lines.mapped("children"))
            reservation.infant_count = sum(lines.mapped("infants"))

            reservation.guest_count = (
                    reservation.adult_count
                    + reservation.child_count
                    + reservation.infant_count
            )

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

    def action_view_invoices(self):
        self.ensure_one()

        invoices = self.folio_ids.mapped("invoice_id").filtered(
            lambda invoice: invoice.move_type == "out_invoice"
        )

        action = {
            "type": "ir.actions.act_window",
            "name": _("Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", invoices.ids)],
            "context": {
                "default_move_type": "out_invoice",
                "create": False,
            },
        }

        if len(invoices) == 1:
            action.update({
                "view_mode": "form",
                "res_id": invoices.id,
            })

        return action

    def _compute_whatsapp_log_count(self):
        Log = self.env["hotel.whatsapp.log"]
        for res in self:
            res.whatsapp_log_count = Log.search_count([
                ("task_reference", "=", f"{res._name},{res.id}")
            ])

    def action_view_whatsapp_logs(self):
        self.ensure_one()
        return {
            "name": _("WhatsApp Notifications"),
            "type": "ir.actions.act_window",
            "res_model": "hotel.whatsapp.log",
            "view_mode": "list,form",
            "domain": [("task_reference", "=", f"{self._name},{self.id}")],
            "context": {
                "default_task_reference": f"{self._name},{self.id}",
                "default_recipient_id": self.partner_id.id,
                "default_phone_number": getattr(self.partner_id, "mobile", False) or self.partner_id.phone or self.guest_phone,
                "default_task_type": "reservation",
                "default_company_id": self.company_id.id,
            },
        }

    def action_send_reservation_whatsapp(self):
        """Manually trigger WhatsApp booking notification for this reservation."""
        self.ensure_one()
        event = "confirmed" if self.state in ("confirmed", "reserved", "checked_in") else "cancelled" if self.state == "cancelled" else "checkout"
        self._notify_reservation(event=event)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("WhatsApp Notification"),
                "message": _("WhatsApp notification has been queued for %s and will be sent shortly.") % self.name,
                "type": "info",
                "sticky": False,
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

        config = self.env["ir.config_parameter"].sudo()

        # ---------------------------------------------------------
        # DEFAULT HOTEL
        # ---------------------------------------------------------

        hotel_id = (
                res.get("hotel_id")
                or self.env.context.get("default_hotel_id")
        )

        if not hotel_id and "hotel_id" in fields_list:
            use_default_hotel = (
                    config.get_param(
                        "vs_hotel_management.use_default_hotel",
                        default="False",
                    ) == "True"
            )

            if use_default_hotel:
                configured_hotel_id = config.get_param(
                    "vs_hotel_management.default_hotel_id"
                )

                if configured_hotel_id:
                    hotel_id = int(configured_hotel_id)
                    res["hotel_id"] = hotel_id

        hotel = (
            self.env["hotel.hotel"].browse(hotel_id).exists()
            if hotel_id
            else self.env["hotel.hotel"]
        )

        # ---------------------------------------------------------
        # CONFIGURED CHECK-IN AND CHECK-OUT TIMES
        # ---------------------------------------------------------

        checkin_time = float(
            config.get_param(
                "vs_hotel_management.checkin_time_default",
                default="14.0",
            )
        )

        checkout_time = float(
            config.get_param(
                "vs_hotel_management.checkout_time_default",
                default="12.0",
            )
        )

        # ---------------------------------------------------------
        # HOTEL TIMEZONE
        # ---------------------------------------------------------

        timezone_name = self.env.user.tz or (hotel and hotel.timezone) or self.env.company.partner_id.tz or "UTC"

        try:
            hotel_timezone = pytz.timezone(timezone_name)
        except pytz.UnknownTimeZoneError:
            hotel_timezone = pytz.UTC

        # ---------------------------------------------------------
        # CONVERT DECIMAL HOURS TO TIME
        # ---------------------------------------------------------

        def to_time(value, label):
            if not 0 <= value < 24:
                raise ValidationError(
                    _("%s must be between 00:00 and 23:59.") % label
                )

            total_minutes = round(value * 60)

            if total_minutes >= 1440:
                raise ValidationError(
                    _("%s must be earlier than 24:00.") % label
                )

            hours, minutes = divmod(total_minutes, 60)
            return datetime.time(hours, minutes)

        checkin_clock = to_time(
            checkin_time,
            _("Default Check-in Time"),
        )

        checkout_clock = to_time(
            checkout_time,
            _("Default Check-out Time"),
        )

        # ---------------------------------------------------------
        # DEFAULT DATES
        # ---------------------------------------------------------

        today = datetime.datetime.now(
            pytz.UTC
        ).astimezone(hotel_timezone).date()

        tomorrow = today + relativedelta(days=1)

        # ---------------------------------------------------------
        # CONVERT HOTEL LOCAL TIME TO UTC
        # ---------------------------------------------------------

        def to_utc(local_date, local_time):
            local_datetime = datetime.datetime.combine(
                local_date,
                local_time,
            )

            try:
                localized = hotel_timezone.localize(
                    local_datetime,
                    is_dst=None,
                )
            except (
                    pytz.AmbiguousTimeError,
                    pytz.NonExistentTimeError,
            ):
                raise ValidationError(
                    _(
                        "The configured time are ambiguous "
                        "or invalid in hotel timezone %s."
                    ) % timezone_name
                )

            return localized.astimezone(
                pytz.UTC
            ).replace(tzinfo=None)

        if "check_in" in fields_list and not res.get("check_in"):
            res["check_in"] = to_utc(today, checkin_clock)

        if "check_out" in fields_list and not res.get("check_out"):
            res["check_out"] = to_utc(tomorrow, checkout_clock)

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
            "booking_date",
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

    # =========================================================
    # NOTIFICATIONS
    # =========================================================

    def _notify_reservation(self, event):
        """
        Dispatch multi-channel notifications (Email, WhatsApp, SMS)
        for reservation events: confirmed, cancelled, checkout, no_show.
        Respects consolidated configuration toggles dynamically.
        """
        ICP = self.env["ir.config_parameter"].sudo()

        def _is_channel_active(new_key, legacy_master_key, legacy_event_key):
            val = ICP.get_param(new_key, None)
            if val is not None:
                return val.lower() in ("true", "1", "yes")
            # Fallback to legacy master & event switches
            master = ICP.get_param(legacy_master_key, "True" if "email" in legacy_master_key else "False").lower() in ("true", "1", "yes")
            event_val = ICP.get_param(legacy_event_key, "True" if "email" in legacy_event_key else "False").lower() in ("true", "1", "yes")
            return master and event_val

        send_email = _is_channel_active(
            "vs_hotel_management.notify_reservation_email",
            "vs_hotel_management.email_enabled",
            f"vs_hotel_management.email_reservation_{event}",
        )
        send_whatsapp = _is_channel_active(
            "vs_hotel_management.notify_reservation_whatsapp",
            "vs_hotel_management.whatsapp_enabled",
            f"vs_hotel_management.whatsapp_reservation_{event}",
        )
        send_sms = _is_channel_active(
            "vs_hotel_management.notify_reservation_sms",
            "vs_hotel_management.sms_enabled",
            f"vs_hotel_management.sms_reservation_{event}",
        )

        for reservation in self:
            partner = reservation.partner_id
            if not partner:
                continue

            phone = getattr(partner, "mobile", False) or partner.phone or reservation.guest_phone or ""
            hotel = reservation.hotel_id
            hotel_name = hotel.name if hotel else _("Hotel")
            currency_symbol = reservation.currency_id.symbol or reservation.currency_id.name or ""

            # -------------------------------------------------
            # 1. CONFIRMATION
            # -------------------------------------------------
            if event == "confirmed":
                # Email
                if send_email:
                    reservation._send_notification_email("vs_hotel_management.mail_template_hotel_reservation_confirmation")

                # WhatsApp
                if send_whatsapp and phone:
                    room_names = ", ".join(reservation.line_ids.mapped("room_id.display_name")) or _("Standard Room")
                    ci = reservation._format_datetime_local(reservation.check_in, partner=partner)
                    co = reservation._format_datetime_local(reservation.check_out, partner=partner)
                    msg = (
                        f"🏨 *{hotel_name}*\n"
                        f"*{_('Reservation Confirmation')}*\n\n"
                        f"{_('Dear')} *{partner.name or _('Guest')}*,\n"
                        f"{_('Thank you for choosing to stay with us. Your reservation is confirmed!')}\n\n"
                        f"📋 *{_('Reservation Ref')}:* {reservation.name}\n"
                        f"📅 *{_('Check-In')}:* {ci}\n"
                        f"📅 *{_('Check-Out')}:* {co}\n"
                        f"🌙 *{_('Duration')}:* {reservation.night_count} {_('Night(s)')}\n"
                        f"👥 *{_('Guests')}:* {reservation.guest_count}\n"
                        f"🛏️ *{_('Rooms')}:* {room_names}\n"
                        f"💰 *{_('Total Amount')}:* {reservation.total_amount:,.2f} {currency_symbol}\n\n"
                        f"{_('We look forward to welcoming you!')}"
                    )
                    reservation._send_whatsapp_message(
                        recipient=phone,
                        message_text=msg,
                        log_values={
                            "recipient_id": partner.id,
                            "task_type": "reservation",
                            "event": "confirmed",
                            "task_reference": f"{reservation._name},{reservation.id}",
                            "message": f"Confirmation WhatsApp message for {reservation.name}",
                        },
                    )

                # SMS
                if send_sms and phone:
                    ci_date = reservation._format_datetime_local(reservation.check_in, partner=partner, dt_format="%d/%m/%Y")
                    co_date = reservation._format_datetime_local(reservation.check_out, partner=partner, dt_format="%d/%m/%Y")
                    sms_msg = _("%(hotel)s: Reservation %(ref)s confirmed from %(ci)s to %(co)s. Total: %(amt).2f %(curr)s. Welcome!") % {
                        "hotel": hotel_name,
                        "ref": reservation.name,
                        "ci": ci_date,
                        "co": co_date,
                        "amt": reservation.total_amount,
                        "curr": currency_symbol,
                    }
                    reservation._send_notification_sms(recipient=phone, message_text=sms_msg)

            # -------------------------------------------------
            # 2. CANCELLATION
            # -------------------------------------------------
            elif event == "cancelled":
                # Email
                if send_email:
                    reservation._send_notification_email("vs_hotel_management.mail_template_hotel_reservation_cancellation")

                # WhatsApp
                if send_whatsapp and phone:
                    ci = reservation._format_datetime_local(reservation.check_in, partner=partner, dt_format="%d %b %Y")
                    co = reservation._format_datetime_local(reservation.check_out, partner=partner, dt_format="%d %b %Y")
                    msg = (
                        f"🏨 *{hotel_name}*\n"
                        f"*{_('Reservation Cancellation Notice')}*\n\n"
                        f"{_('Dear')} *{partner.name or _('Guest')}*,\n"
                        f"{_('Your reservation')} *{reservation.name}* ({ci} - {co}) {_('has been cancelled.')}\n\n"
                        f"{_('If you have questions or require further assistance, please contact our front desk team.')}"
                    )
                    reservation._send_whatsapp_message(
                        recipient=phone,
                        message_text=msg,
                        log_values={
                            "recipient_id": partner.id,
                            "task_type": "reservation",
                            "event": "cancelled",
                            "task_reference": f"{reservation._name},{reservation.id}",
                            "message": f"Cancellation WhatsApp message for {reservation.name}",
                        },
                    )

                # SMS
                if send_sms and phone:
                    sms_msg = _("%(hotel)s: Your reservation %(ref)s has been cancelled. Please contact our front desk for assistance.") % {
                        "hotel": hotel_name,
                        "ref": reservation.name,
                    }
                    reservation._send_notification_sms(recipient=phone, message_text=sms_msg)

            # -------------------------------------------------
            # 3. CHECKOUT & FOLIO
            # -------------------------------------------------
            elif event == "checkout":
                folio = reservation.folio_ids.filtered(lambda f: f.state != "cancelled")[:1]
                folio_name = folio.name if folio else _("Folio")
                total_charges = folio.total_amount if folio else reservation.total_amount
                paid_amount = folio.paid_amount if folio else 0.0
                balance_amount = folio.balance_amount if folio else 0.0

                # Email
                if send_email:
                    if folio:
                        folio._send_notification_email("vs_hotel_management.mail_template_hotel_guest_folio")
                    else:
                        reservation._send_notification_email("vs_hotel_management.mail_template_hotel_reservation_checkout")

                # WhatsApp
                if send_whatsapp and phone:
                    msg = (
                        f"🏨 *{hotel_name}*\n"
                        f"*{_('Thank You for Staying with Us!')}*\n\n"
                        f"{_('Dear')} *{partner.name or _('Guest')}*,\n"
                        f"{_('We hope you enjoyed your stay at')} *{hotel_name}*.\n"
                        f"{_('Your checkout is complete.')}\n\n"
                        f"📋 *{_('Reservation Ref')}:* {reservation.name}\n"
                        f"🧾 *{_('Folio Number')}:* {folio_name}\n"
                        f"💵 *{_('Total Charges')}:* {total_charges:,.2f} {currency_symbol}\n"
                        f"💳 *{_('Total Paid')}:* {paid_amount:,.2f} {currency_symbol}\n"
                        f"⚖️ *{_('Outstanding Balance')}:* {balance_amount:,.2f} {currency_symbol}\n\n"
                        f"{_('Thank you for choosing us, and we look forward to welcoming you back again soon. Safe travels!')}"
                    )
                    reservation._send_whatsapp_message(
                        recipient=phone,
                        message_text=msg,
                        log_values={
                            "recipient_id": partner.id,
                            "task_type": "reservation",
                            "event": "checkout",
                            "task_reference": f"{reservation._name},{reservation.id}",
                            "message": f"Checkout thank-you & folio summary sent for {reservation.name}",
                        },
                    )

                # SMS
                if send_sms and phone:
                    sms_msg = _("Thank you for staying at %(hotel)s! %(ref)s charges: %(tot).2f %(curr)s, Balance: %(bal).2f %(curr)s. Safe travels!") % {
                        "hotel": hotel_name,
                        "ref": reservation.name,
                        "tot": total_charges,
                        "bal": balance_amount,
                        "curr": currency_symbol,
                    }
                    reservation._send_notification_sms(recipient=phone, message_text=sms_msg)

            # -------------------------------------------------
            # 4. NO SHOW
            # -------------------------------------------------
            elif event == "no_show":
                # Email
                if send_email:
                    reservation._send_notification_email("vs_hotel_management.mail_template_hotel_reservation_noshow")

                # WhatsApp
                if send_whatsapp and phone:
                    ci = reservation._format_datetime_local(reservation.check_in, partner=partner)
                    msg = (
                        f"🏨 *{hotel_name}*\n"
                        f"*{_('Reservation No-Show Notification')}*\n\n"
                        f"{_('Dear')} *{partner.name or _('Guest')}*,\n"
                        f"{_('We noted that you were unable to check in for your reservation')} *{reservation.name}* ({ci}).\n\n"
                        f"{_('If you need to reschedule or require assistance, please contact our front desk team.')}"
                    )
                    reservation._send_whatsapp_message(
                        recipient=phone,
                        message_text=msg,
                        log_values={
                            "recipient_id": partner.id,
                            "task_type": "reservation",
                            "event": "no_show",
                            "task_reference": f"{reservation._name},{reservation.id}",
                            "message": f"No-show notice sent for {reservation.name}",
                        },
                    )

                # SMS
                if send_sms and phone:
                    sms_msg = _("%(hotel)s: Reservation %(ref)s marked as No-Show. Please contact front desk if you need assistance.") % {
                        "hotel": hotel_name,
                        "ref": reservation.name,
                    }
                    reservation._send_notification_sms(recipient=phone, message_text=sms_msg)

    # =========================================================
    # WORKFLOW
    # =========================================================

    def action_confirm(self):
        """Confirm the reservation without creating room bookings."""
        # Pre-validate reservation lines and rooms before prompting for guest ID
        for reservation in self:
            if reservation.state != "draft":
                raise UserError(
                    _("Only draft reservations can be confirmed.")
                )

            if not reservation.line_ids:
                raise ValidationError(
                    _("A reservation must contain at least one room before it can be confirmed.")
                )

            for line in reservation.line_ids:
                if not line.room_id:
                    raise ValidationError(
                        _("Each reservation line must have a room.")
                    )

        # Prompt for guest identification if required and missing
        if len(self) == 1 and not self.env.context.get("skip_guest_id_check"):
            res = self[0]
            require_guest_id = (
                res.hotel_id.require_guest_identification
                or (self.env["ir.config_parameter"].sudo().get_param("vs_hotel_management.require_guest_id", "False").lower() in ("true", "1"))
            )
            guest = res.partner_id
            guest_id_num = (guest and guest.id_number) or getattr(res, "id_number", False)
            if require_guest_id and not guest_id_num:
                guest_country = (guest and guest.nationality) or getattr(res, "id_country_id", False)
                return {
                    "name": _("Guest Identification Details"),
                    "type": "ir.actions.act_window",
                    "res_model": "hotel.guest.id.wizard",
                    "view_mode": "form",
                    "target": "new",
                    "context": {
                        "default_reservation_id": res.id,
                        "default_partner_id": guest.id if guest else False,
                        "default_id_type": (guest and guest.id_type) or getattr(res, "id_type", "national_id"),
                        "default_id_number": guest_id_num or "",
                        "default_id_country_id": guest_country.id if guest_country else False,
                        "default_date_of_birth": (guest and guest.date_of_birth) or getattr(res, "date_of_birth", False),
                        "default_gender": (guest and guest.gender) or getattr(res, "gender", False),
                    },
                }

        for reservation in self:
            room_ids = reservation.line_ids.mapped("room_id").ids
            if room_ids:
                self.env.cr.execute(
                    "SELECT id FROM hotel_room WHERE id IN %s FOR UPDATE",
                    (tuple(room_ids),),
                )

            reservation._validate_reservation()

            reservation.state = "confirmed"
            reservation._notify_reservation(event="confirmed")

        return True

    # =========================================================
    # RESERVE
    # =========================================================

    def action_reserve(self):
        """Validate room availability and reserve the selected rooms."""

        RoomBooking = self.env["hotel.room.booking"]

        for reservation in self:
            if reservation.state not in ("confirmed", "draft"):
                raise UserError(
                    _("Only draft or confirmed reservations can be reserved.")
                )

            if not reservation.line_ids:
                raise UserError(
                    _(
                        "At least one reservation line is required "
                        "before reserving the reservation."
                    )
                )

            # Ensure every line has a room and valid dates.
            for line in reservation.line_ids:
                if not line.room_id:
                    raise ValidationError(
                        _("Each reservation line must have a room.")
                    )

                if not line.check_in or not line.check_out:
                    raise ValidationError(
                        _("Check-in and check-out dates are required.")
                    )

                if line.check_out <= line.check_in:
                    raise ValidationError(
                        _("Check-out must be later than check-in.")
                    )

            # Lock selected rooms to reduce concurrent booking conflicts.
            room_ids = reservation.line_ids.mapped("room_id").ids

            if room_ids:
                self.env.cr.execute(
                    """
                    SELECT id
                    FROM hotel_room
                    WHERE id IN %s
                    ORDER BY id
                        FOR UPDATE
                    """,
                    (tuple(room_ids),),
                )

                # Refresh status after acquiring the database locks.
                rooms = reservation.line_ids.mapped("room_id")
                rooms.invalidate_recordset(["status"])

            # Validate reservation dates, capacity, and other existing rules.
            reservation._validate_reservation()

            # Validate ALL rooms before creating any bookings.
            for line in reservation.line_ids:
                room = line.room_id

                if room.status != "available":
                    raise UserError(
                        _(
                            "Room %(room)s is not available. "
                            "Its current status is '%(status)s'. "
                            "Please select an available room."
                        )
                        % {
                            "room": room.display_name,
                            "status": room.status,
                        }
                    )

                # Find active bookings for this room that overlap
                # the requested stay in another reservation.
                overlapping_booking = RoomBooking.search(
                    [
                        ("room_id", "=", room.id),
                        ("reservation_id", "!=", reservation.id),
                        ("state", "in", ["reserved", "checked_in"]),
                        ("reservation_id.state", "in", ["reserved", "checked_in"]),
                        ("check_in", "<", line.check_out),
                        ("check_out", ">", line.check_in),
                    ],
                    limit=1,
                )

                if overlapping_booking:
                    raise UserError(
                        _(
                            "Room %(room)s is already allocated to another "
                            "reservation during the requested dates."
                        )
                        % {
                            "room": room.display_name,
                        }
                    )

            # All rooms have passed validation. Create missing bookings.
            reservation.line_ids._create_room_booking()

            # Change room statuses only after validation and booking creation.
            reservation.line_ids.mapped("room_id").write({
                "status": "reserved",
            })

            reservation.state = "reserved"

        return True

    # =========================================================
    # CHECK IN
    # =========================================================

    def action_check_in(self):
        """Check in reserved room bookings and create the guest folio."""
        config = self.env["ir.config_parameter"].sudo()

        allow_early_checkin = (
                config.get_param(
                    "vs_hotel_management.allow_early_checkin",
                    default="False",
                ) == "True"
        )

        for reservation in self:
            if reservation.state != "reserved":
                raise UserError(
                    _("Only reserved reservations can be checked in.")
                )

            hotel = reservation.hotel_id

            # -------------------------------------------------
            # Validate Scheduled Check-in Time
            # -------------------------------------------------
            if not allow_early_checkin and reservation.check_in:
                timezone_name = (
                    hotel.timezone
                    if hotel and hotel.timezone
                    else "UTC"
                )

                try:
                    hotel_timezone = pytz.timezone(timezone_name)
                except pytz.UnknownTimeZoneError:
                    raise UserError(
                        _("Invalid hotel timezone: %s") % timezone_name
                    )

                current_datetime = fields.Datetime.to_datetime(
                    fields.Datetime.now()
                )
                scheduled_checkin = fields.Datetime.to_datetime(
                    reservation.check_in
                )

                current_local_time = pytz.UTC.localize(
                    current_datetime
                ).astimezone(hotel_timezone)

                scheduled_local_time = pytz.UTC.localize(
                    scheduled_checkin
                ).astimezone(hotel_timezone)

                if current_local_time < scheduled_local_time:
                    raise UserError(
                        _(
                            "Early check-in is not allowed. "
                            "The scheduled check-in time is %(checkin)s "
                            "(hotel local time)."
                        ) % {
                            "checkin": scheduled_local_time.strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        }
                    )

            # -------------------------------------------------
            # Lock Room Rows
            # -------------------------------------------------
            room_ids = reservation.line_ids.mapped("room_id").ids

            if room_ids:
                self.env.cr.execute(
                    """
                    SELECT id
                    FROM hotel_room
                    WHERE id IN %s
                    ORDER BY id
                        FOR UPDATE
                    """,
                    (tuple(sorted(room_ids)),),
                )

                self.env["hotel.room"].browse(
                    room_ids
                ).invalidate_recordset(["status"])

            # -------------------------------------------------
            # Validate Reservation
            # -------------------------------------------------
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
            # Check In Room Bookings
            # -------------------------------------------------
            bookings.action_check_in()

            # -------------------------------------------------
            # Create or Open Guest Folio
            # -------------------------------------------------
            reservation._create_guest_folio()

            # -------------------------------------------------
            # Update Reservation State
            # -------------------------------------------------
            reservation.state = "checked_in"

        return True

    # =========================================================
    # CHECK OUT
    # =========================================================

    def action_check_out(self):
        """Check out all rooms belonging to the reservation."""
        config = self.env["ir.config_parameter"].sudo()

        allow_early_checkout = (
                config.get_param(
                    "vs_hotel_management.allow_early_checkout",
                    default="False",
                ) == "True"
        )

        auto_create_invoice = (
                config.get_param(
                    "vs_hotel_management.auto_create_invoice",
                    default="False",
                ) == "True"
        )

        for reservation in self:
            if reservation.state != "checked_in":
                raise UserError(
                    _("Only checked-in reservations can be checked out.")
                )

            hotel = reservation.hotel_id

            # -------------------------------------------------
            # Validate Scheduled Checkout Time
            # -------------------------------------------------
            if not allow_early_checkout and reservation.check_out:
                timezone_name = (
                    hotel.timezone
                    if hotel and hotel.timezone
                    else "UTC"
                )

                try:
                    hotel_timezone = pytz.timezone(timezone_name)
                except pytz.UnknownTimeZoneError:
                    raise UserError(
                        _("Invalid hotel timezone: %s") % timezone_name
                    )

                current_datetime = fields.Datetime.to_datetime(
                    fields.Datetime.now()
                )
                scheduled_checkout = fields.Datetime.to_datetime(
                    reservation.check_out
                )

                current_local_time = pytz.UTC.localize(
                    current_datetime
                ).astimezone(hotel_timezone)

                scheduled_local_time = pytz.UTC.localize(
                    scheduled_checkout
                ).astimezone(hotel_timezone)

                if current_local_time < scheduled_local_time:
                    raise UserError(
                        _(
                            "Early checkout is not allowed. "
                            "Checkout is available from %(checkout)s "
                            "(hotel local time)."
                        ) % {
                            "checkout": scheduled_local_time.strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        }
                    )

            # -------------------------------------------------
            # Check Out Room Bookings
            # -------------------------------------------------
            bookings = reservation.line_ids.mapped(
                "room_booking_id"
            ).filtered(
                lambda booking: booking.state == "checked_in"
            )

            if not bookings:
                raise UserError(
                    _("There are no checked-in rooms to check out.")
                )

            bookings.action_check_out()

            # -------------------------------------------------
            # Finalize Guest Folio
            # -------------------------------------------------
            folio = reservation.folio_ids.filtered(
                lambda item: item.state in ("open", "partially_paid")
            )[:1]

            if folio:
                reservation._create_folio_service_charges(folio)

                if auto_create_invoice and not folio.invoice_id:
                    folio.action_create_invoice()

            # -------------------------------------------------
            # Update Reservation State
            # -------------------------------------------------
            reservation.state = "checked_out"
            reservation._notify_reservation(event="checkout")

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
    # COMPLETE
    # =========================================================

    def action_complete(self):
        """Complete the reservation after checkout, folio payment validation, and auto-closing folios."""
        for reservation in self:
            if reservation.state != "checked_out":
                raise UserError(
                    _(
                        "Only checked-out reservations "
                        "can be completed."
                    )
                )

            bookings = reservation.line_ids.mapped(
                "room_booking_id"
            ).filtered(
                lambda booking: booking.state == "checked_out"
            )

            if not bookings:
                raise UserError(
                    _("There are no checked-out rooms to complete.")
                )

            # Validate that non-cancelled guest folios exist
            folios = reservation.folio_ids.filtered(
                lambda f: f.state != "cancelled"
            )

            if not folios:
                raise UserError(
                    _(
                        "The reservation cannot be completed "
                        "because no guest folio exists."
                    )
                )

            # Ensure latest amounts and payment states are recalculated
            folios._compute_amounts()
            folios._sync_folio_payment_state()

            # Validate that all active folios are in 'paid' status (or already closed)
            unpaid_folios = folios.filtered(lambda f: f.state not in ("paid", "closed"))
            if unpaid_folios:
                status_labels = dict(self.env["hotel.guest.folio"]._fields["state"].selection)
                details = ", ".join(
                    f"{f.name} ({status_labels.get(f.state, f.state)} - Balance: {f.balance_amount:,.2f})"
                    for f in unpaid_folios
                )
                raise UserError(
                    _(
                        "The reservation cannot be completed because the guest folio is not in 'Paid' status.\n\n"
                        "Unpaid Folio(s): %s\n\n"
                        "Please settle the full payment before completing the reservation."
                    )
                    % details
                )

            # Transition folios from 'paid' to 'closed'
            for folio in folios:
                if folio.state == "paid":
                    folio.action_close()

            # Complete room bookings only after validation passes.
            bookings.action_complete()

            # Update reservation state.
            reservation.state = "completed"

        return True

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

            reservation.state = "cancelled"
            reservation._notify_reservation(event="cancelled")

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
            reservation._notify_reservation(event="no_show")

        return True

    # =========================================================
    # RESET TO DRAFT
    # =========================================================

    def action_reset_to_draft(self):
        for reservation in self:
            if reservation.state not in (
                    "confirmed",
                    "reserved",
                    "cancelled",
                    "no_show",
            ):
                raise UserError(
                    _(
                        "This reservation cannot be reset to draft "
                        "from its current state."
                    )
                )

            # Reset related room bookings.
            bookings_to_reset = reservation.room_booking_ids.filtered(
                lambda booking: booking.state in (
                    "reserved",
                    "cancelled",
                    "released",
                )
            )

            bookings_to_reset.write({
                "state": "reserved",
            })

            if reservation.state != "confirmed":
                bookings_to_reset.room_id.write({
                    "status": "available",
                })

            reservation.state = "draft"

        return True
    
    # =========================================================
    # VALIDATION
    # =========================================================
    def _validate_reservation(self, for_check_in=False):
        """Validate reservation and its lines before confirmation,
        reservation, or check-in.
        """
        self.ensure_one()

        config = self.env["ir.config_parameter"].sudo()

        def get_bool(key, default=False):
            value = config.get_param(
                "vs_hotel_management.%s" % key,
                default=str(default),
            )
            return str(value).lower() in ("true", "1", "yes")

        if not self.partner_id:
            raise ValidationError(_("A guest is required."))

        if not self.hotel_id:
            raise ValidationError(_("A hotel is required."))

        if not self.check_in:
            raise ValidationError(_("Check-in is required."))

        if not self.check_out:
            raise ValidationError(_("Check-out is required."))

        if self.check_out <= self.check_in:
            raise ValidationError(
                _("Check-out must be later than check-in.")
            )

        # -------------------------------------------------
        # Guest Identification
        # -------------------------------------------------
        require_guest_id = (
                self.hotel_id.require_guest_identification
                or get_bool("require_guest_id")
        )

        if require_guest_id and not (self.partner_id.id_number or getattr(self, "id_number", False)):
            if not self.env.context.get("skip_guest_id_check"):
                raise ValidationError(
                    _(
                        "Guest identification (ID Number) is required "
                        "for reservations at %s."
                    ) % self.hotel_id.name
                )

        if not self.line_ids:
            raise ValidationError(
                _("At least one reservation line is required.")
            )

        # -------------------------------------------------
        # Minimum and Maximum Stay
        # -------------------------------------------------
        minimum_stay, maximum_stay = self._get_stay_limits()

        if self.night_count < minimum_stay:
            raise ValidationError(
                _(
                    "The reservation must be at least %s night(s)."
                ) % minimum_stay
            )

        if self.night_count > maximum_stay:
            raise ValidationError(
                _(
                    "The reservation cannot exceed %s night(s)."
                ) % maximum_stay
            )

        # -------------------------------------------------
        # Duplicate Rooms
        # -------------------------------------------------
        self._check_duplicate_rooms()

        # -------------------------------------------------
        # Overbooking
        # -------------------------------------------------
        global_allow_overbooking = get_bool("allow_overbooking")

        hotel_allow_overbooking = self.hotel_id.allow_overbooking

        allow_overbooking = (
                global_allow_overbooking or hotel_allow_overbooking
        )

        # -------------------------------------------------
        # Validate Reservation Lines
        # -------------------------------------------------
        for line in self.line_ids:
            line._validate_reservation_line(
                for_check_in=for_check_in,
                allow_overbooking=allow_overbooking,
            )

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

    _hotel_reservation_name_unique = models.Constraint(
        'unique(name, company_id)',
        "Reservation reference must be unique.",
    )
