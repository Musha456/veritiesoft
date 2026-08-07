from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    checkin_time_default = fields.Float(
        string="Default Check-in Time",
        config_parameter="vs_hotel_management.checkin_time_default",
        default=14.0,
    )

    checkout_time_default = fields.Float(
        string="Default Check-out Time",
        config_parameter="vs_hotel_management.checkout_time_default",
        default=12.0,
    )

    allow_overbooking = fields.Boolean(
        string="Allow Overbooking",
        config_parameter="vs_hotel_management.allow_overbooking",
    )

    require_guest_id = fields.Boolean(
        string="Require Guest Identification",
        config_parameter="vs_hotel_management.require_guest_id",
        default=True,
    )

    allow_early_checkin = fields.Boolean(
        string="Allow Early Check-in",
        config_parameter="vs_hotel_management.allow_early_checkin",
    )

    allow_late_checkout = fields.Boolean(
        string="Allow Late Check-out",
        config_parameter="vs_hotel_management.allow_late_checkout",
    )

    auto_generate_room_number = fields.Boolean(
        string="Generate Room Numbers Automatically",
        config_parameter="vs_hotel_management.auto_generate_room_number",
    )

    auto_generate_building_code = fields.Boolean(
        string="Generate Building Codes Automatically",
        config_parameter="vs_hotel_management.auto_generate_building_code",
        default=True,
    )

    auto_generate_floor_code = fields.Boolean(
        string="Generate Floor Codes Automatically",
        config_parameter="vs_hotel_management.auto_generate_floor_code",
        default=True,
    )

    auto_generate_room_category_code = fields.Boolean(
        string="Generate Room Category Codes Automatically",
        config_parameter="vs_hotel_management.auto_generate_room_category_code",
        default=True,
    )