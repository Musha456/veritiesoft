# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    enable_multiple_hotel_support = fields.Boolean(
        string="Enable Multiple Hotel Support",
        default=True,
        help="When enabled, guests can browse and filter from all available hotel properties in a card layout. When disabled, only the default primary hotel's room types are displayed.",
    )

    default_hotel_id = fields.Many2one(
        "hotel.hotel",
        string="Default Primary Hotel",
        help="The primary default hotel property pre-selected in online reservation searches.",
    )

    hotel_banner_image = fields.Image(
        string="Main Booking Banner Image",
        max_width=1920,
        max_height=1080,
        help="Hero banner image displayed on the website homepage and online booking engine. A placeholder is used if not configured.",
    )

    hotel_banner_title = fields.Char(
        string="Banner Title",
        translate=True,
        default="Discover Extraordinary Stays & Luxury Escapes",
        help="Main headline text displayed on the website hero banner.",
    )

    hotel_banner_subtitle = fields.Char(
        string="Banner Subtitle",
        translate=True,
        default="Book your stay directly for exclusive best-rate guarantees, personalized service, and flexible check-in.",
        help="Subheading text displayed beneath the headline on the hero banner.",
    )

    advance_booking_payment_policy = fields.Selection(
        [
            ("optional", "Optional (Guest may pay advance or choose Pay Later at Hotel)"),
            ("mandatory", "Mandatory (Guest must pay advance online to book)"),
        ],
        string="Advance Payment Policy",
        default="optional",
        help="Determines whether online booking requires an advance payment.",
    )

    advance_booking_percentage = fields.Float(
        string="Advance Payment Percentage (%)",
        default=30.0,
        help="Percentage of the room total required when paying an advance deposit.",
    )

    allow_guest_room_change = fields.Boolean(
        string="Allow Room Change in Guest Portal",
        default=True,
        help="Allows guests to switch their assigned room in the portal to any available room before check-in.",
    )
