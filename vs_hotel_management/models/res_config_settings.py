from odoo import fields, models
import logging
_logger = logging.getLogger(__name__)


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
    )

    auto_generate_floor_code = fields.Boolean(
        string="Generate Floor Codes Automatically",
        config_parameter="vs_hotel_management.auto_generate_floor_code",
    )

    auto_generate_room_category_code = fields.Boolean(
        string="Generate Room Category Codes Automatically",
        config_parameter="vs_hotel_management.auto_generate_room_category_code",
    )

    mark_room_dirty_on_checkout = fields.Boolean(
        string="Mark Room Dirty on Checkout",
        config_parameter="vs_hotel_management.mark_room_dirty_on_checkout",
    )

    def set_values(self):
        _logger.warning(
            "MARK ROOM DIRTY BEFORE SAVE: value=%r, type=%s",
            self.mark_room_dirty_on_checkout,
            type(self.mark_room_dirty_on_checkout).__name__,
        )

        res = super().set_values()

        value = self.env['ir.config_parameter'].sudo().get_param(
            'vs_hotel_management.mark_room_dirty_on_checkout'
        )

        _logger.warning(
            "MARK ROOM DIRTY AFTER SAVE: value=%r, type=%s",
            value,
            type(value).__name__,
        )

        return res