# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class HotelReservation(models.Model):
    _inherit = "hotel.reservation"

    accompanying_guest_ids = fields.One2many(
        "hotel.reservation.guest",
        "reservation_id",
        string="Accompanying Guests",
    )

    accompanying_guest_count = fields.Integer(
        string="Accompanying Count",
        compute="_compute_accompanying_guest_count",
    )

    advance_payment_choice = fields.Selection(
        [
            ("advance", "Advance Deposit Paid"),
            ("full", "Full Amount Paid Online"),
            ("pay_at_hotel", "Pay Later at Hotel"),
        ],
        string="Payment Choice",
        default="pay_at_hotel",
        tracking=True,
    )

    advance_payment_amount = fields.Monetary(
        string="Advance Required",
        currency_field="currency_id",
        help="Calculated advance payment amount for this reservation.",
    )

    advance_paid_amount = fields.Monetary(
        string="Advance Paid",
        currency_field="currency_id",
        default=0.0,
        tracking=True,
    )

    advance_payment_status = fields.Selection(
        [
            ("unpaid", "Unpaid"),
            ("paid", "Paid Online"),
            ("pay_at_hotel", "Pay at Hotel"),
        ],
        string="Advance Payment Status",
        default="pay_at_hotel",
        tracking=True,
    )

    is_online_booking = fields.Boolean(
        string="Online Booking",
        default=False,
    )

    @api.depends("accompanying_guest_ids")
    def _compute_accompanying_guest_count(self):
        for res in self:
            res.accompanying_guest_count = len(res.accompanying_guest_ids)

    def action_switch_line_room(self, line_id, new_room_id):
        """
        Public / Portal method: Switch an assigned room to another available room before check-in.
        """
        self.ensure_one()
        if self.state not in ("draft", "confirmed"):
            raise UserError(_("Rooms can only be changed before check-in."))

        line = self.line_ids.filtered(lambda l: l.id == line_id)
        if not line:
            raise UserError(_("Reservation room line not found."))

        new_room = self.env["hotel.room"].browse(new_room_id)
        if not new_room.exists():
            raise UserError(_("Selected room does not exist."))

        if new_room.hotel_id != self.hotel_id:
            raise UserError(_("Room belongs to a different hotel property."))

        # Check availability
        is_avail = new_room.is_available(
            check_in=line.check_in,
            check_out=line.check_out,
            current_reservation=self,
            raise_exception=True,
        )
        if not is_avail:
            raise UserError(_("Room %s is not available for the selected dates.") % new_room.display_name)

        old_room_name = line.room_id.display_name
        line.write({
            "room_id": new_room.id,
            "room_category_id": new_room.room_category_id.id,
            "building_id": new_room.building_id.id if new_room.building_id else False,
            "floor_id": new_room.floor_id.id if new_room.floor_id else False,
        })

        # Update room booking if it was already created
        if line.room_booking_id:
            line.room_booking_id.write({
                "room_id": new_room.id,
            })

        self.message_post(
            body=_("Room changed from <b>%s</b> to <b>%s</b> via Guest Portal.") % (old_room_name, new_room.display_name)
        )

        # Queue room switch notification email to hotel management
        try:
            template = self.env.ref("vs_hotel_booking_engine.mail_template_hotel_room_change_manager", raise_if_not_found=False)
            if template:
                template.send_mail(self.id, force_send=False)
        except Exception as e:
            _logger.warning("Could not queue room change notification email: %s", e)

        return True

    def get_available_switch_rooms(self, line_id):
        """Returns list of available rooms that this line can be switched to."""
        self.ensure_one()
        line = self.line_ids.filtered(lambda l: l.id == line_id)
        if not line:
            return []

        # Find operational rooms in this hotel
        domain = [
            ("hotel_id", "=", self.hotel_id.id),
            ("building_id.status", "in", ("operational", False)),
            ("id", "!=", line.room_id.id),
        ]
        candidate_rooms = self.env["hotel.room"].search(domain)
        available = []
        for r in candidate_rooms:
            if r.is_available(check_in=line.check_in, check_out=line.check_out, current_reservation=self, raise_exception=False):
                available.append({
                    "id": r.id,
                    "room_number": r.room_number,
                    "name": r.display_name,
                    "floor": r.floor_id.name if r.floor_id else "",
                    "bed_type": r.bed_type_id.name if r.bed_type_id else "",
                })
        return available

    def action_portal_cancel(self, reason=None):
        """
        Self-service portal cancellation: Allows guest to cancel their reservation online
        prior to arrival, releasing rooms and notifying front desk.
        """
        self.ensure_one()
        if self.state not in ("draft", "confirmed"):
            raise UserError(_("Only draft or confirmed reservations can be cancelled online."))

        # Release rooms
        for line in self.line_ids:
            line.sudo()._cancel_room_booking()
            line.sudo().write({"state": "cancelled"})

        cancel_msg = _("Reservation cancelled online by guest via Guest Portal.")
        if reason:
            cancel_msg += f"<br/><b>Reason:</b> {reason}"

        self.sudo().write({
            "state": "cancelled",
        })
        self.message_post(body=cancel_msg)
        self._notify_reservation(event="cancelled")
        return True

    def send_online_booking_queued_emails(self):
        """
        Queues both the Guest Thank-You email and the Hotel Management notification email
        asynchronous in Odoo's mail.mail queue for optimal checkout performance.
        """
        self.ensure_one()
        try:
            # 1. Thank-you email to guest
            guest_template = self.env.ref(
                "vs_hotel_booking_engine.mail_template_hotel_booking_guest_thankyou",
                raise_if_not_found=False
            )
            if guest_template and self.partner_id.email:
                guest_template.send_mail(self.id, force_send=False)

            # 2. Notification email to hotel management
            mgr_template = self.env.ref(
                "vs_hotel_booking_engine.mail_template_hotel_booking_manager_notification",
                raise_if_not_found=False
            )
            if mgr_template:
                mgr_template.send_mail(self.id, force_send=False)
        except Exception as e:
            _logger.warning("Could not queue online booking emails for reservation %s: %s", self.name, e)
