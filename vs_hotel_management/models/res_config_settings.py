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

    allow_early_checkin = fields.Boolean(
        string="Allow Early Check-in",
        config_parameter="vs_hotel_management.allow_early_checkin",
    )

    allow_late_checkout = fields.Boolean(
        string="Allow Late Check-out",
        config_parameter="vs_hotel_management.allow_late_checkout",
    )



    mark_room_dirty_on_checkout = fields.Boolean(
        string="Mark Room Dirty on Checkout",
        config_parameter="vs_hotel_management.mark_room_dirty_on_checkout",
    )

    # ---------------------------------------------------------
    # Reservation Automation
    # ---------------------------------------------------------

    hotel_auto_confirm_reservation = fields.Boolean(
        string="Auto-confirm Reservations",
        default=False,
        config_parameter="vs_hotel_management.auto_confirm_reservation",
    )


    hotel_auto_create_invoice = fields.Boolean(
        string="Auto-create Invoice",
        default=False,
        config_parameter="vs_hotel_management.auto_create_invoice",
    )


    hotel_require_payment_before_checkout = fields.Boolean(
        string="Require Payment Before Checkout",
        default=False,
        config_parameter="vs_hotel_management.require_payment_before_checkout",
    )

    hotel_auto_close_folio_after_payment = fields.Boolean(
        string="Auto-close Folio After Payment",
        default=True,
        config_parameter="vs_hotel_management.auto_close_folio_after_payment",
    )

    # ---------------------------------------------------------
    # Room Automation
    # ---------------------------------------------------------


    hotel_auto_available_room = fields.Boolean(
        string="Mark Room Available After Cleaning",
        default=True,
        config_parameter="vs_hotel_management.auto_available_room",
    )

    # ---------------------------------------------------------
    # Reservation Rules
    # ---------------------------------------------------------

    hotel_require_guest = fields.Boolean(
        string="Require Guest",
        default=True,
        config_parameter="vs_hotel_management.require_guest",
    )

    hotel_require_rate_plan = fields.Boolean(
        string="Require Rate Plan",
        default=True,
        config_parameter="vs_hotel_management.require_rate_plan",
    )

    hotel_minimum_stay = fields.Integer(
        string="Minimum Stay (Nights)",
        default=1,
        config_parameter="vs_hotel_management.minimum_stay",
    )

    hotel_maximum_stay = fields.Integer(
        string="Maximum Stay (Nights)",
        default=365,
        config_parameter="vs_hotel_management.maximum_stay",
    )