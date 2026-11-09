# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

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
