# -*- coding: utf-8 -*-
from odoo import fields, models


class HotelReservationGuest(models.Model):
    _name = "hotel.reservation.guest"
    _description = "Accompanying Reservation Guest"
    _order = "id asc"

    reservation_id = fields.Many2one(
        "hotel.reservation",
        string="Reservation",
        required=True,
        ondelete="cascade",
        index=True,
    )

    name = fields.Char(
        string="Full Name",
        required=True,
    )

    id_type = fields.Selection(
        [
            ("national_id", "National ID / CNIC"),
            ("cnic", "CNIC / National ID"),
            ("passport", "Passport"),
            ("driving_license", "Driving License"),
            ("other", "Other"),
        ],
        string="ID Type",
        default="cnic",
    )

    id_number = fields.Char(
        string="ID Number / CNIC",
    )

    age_category = fields.Selection(
        [
            ("adult", "Adult"),
            ("child", "Child"),
        ],
        string="Age Category",
        default="adult",
    )

    gender = fields.Selection(
        [
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
        ],
        string="Gender",
    )

    phone = fields.Char(
        string="Phone / Mobile",
    )
