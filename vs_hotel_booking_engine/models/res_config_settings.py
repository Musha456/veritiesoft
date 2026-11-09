# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

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
