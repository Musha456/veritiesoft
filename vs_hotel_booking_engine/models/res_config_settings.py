# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    enable_multiple_hotel_support = fields.Boolean(
        related="company_id.enable_multiple_hotel_support",
        readonly=False,
    )

    booking_default_hotel_id = fields.Many2one(
        related="company_id.default_hotel_id",
        readonly=False,
        string="Default Primary Hotel",
    )

    hotel_banner_image = fields.Image(
        related="company_id.hotel_banner_image",
        readonly=False,
        string="Main Booking Banner Image",
    )

    hotel_banner_title = fields.Char(
        related="company_id.hotel_banner_title",
        readonly=False,
        string="Banner Title",
    )

    hotel_banner_subtitle = fields.Char(
        related="company_id.hotel_banner_subtitle",
        readonly=False,
        string="Banner Subtitle",
    )

    advance_booking_payment_policy = fields.Selection(
        related="company_id.advance_booking_payment_policy",
        readonly=False,
    )

    advance_booking_percentage = fields.Float(
        related="company_id.advance_booking_percentage",
        readonly=False,
    )

    allow_guest_room_change = fields.Boolean(
        related="company_id.allow_guest_room_change",
        readonly=False,
    )
