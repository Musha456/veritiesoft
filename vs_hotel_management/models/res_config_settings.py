from odoo import fields, models, api
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

    allow_early_checkout = fields.Boolean(
        string="Allow Early Checkout",
        config_parameter="vs_hotel_management.allow_early_checkout",
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

    allow_room_add_reserved = fields.Boolean(
        string="Allow Adding Rooms to Reserved Reservations",
        config_parameter="vs_hotel_management.allow_room_add_reserved",
        help="Allow users to add room lines to reservations that are in the Reserved state.",
    )

    # ---------------------------------------------------------
    # DEFAULT HOTEL, BUILDING AND FLOOR
    # ---------------------------------------------------------

    use_default_hotel = fields.Boolean(
        string="Use Default Hotel",
    )

    configured_hotel_id = fields.Many2one(
        "hotel.hotel",
        string="Default Hotel",
    )

    use_default_building = fields.Boolean(
        string="Use Default Building",
    )

    configured_building_id = fields.Many2one(
        "hotel.building",
        string="Default Building",
        domain="[('hotel_id', '=', configured_hotel_id)]",
    )

    use_default_floor = fields.Boolean(
        string="Use Default Floor",
    )

    configured_floor_id = fields.Many2one(
        "hotel.building.floor",
        string="Default Floor",
        domain="[('building_id', '=', configured_building_id)]",
    )

    # ---------------------------------------------------------
    # GET CONFIGURATION VALUES
    # ---------------------------------------------------------

    @api.model
    def get_values(self):
        res = super().get_values()
        config = self.env["ir.config_parameter"].sudo()

        res.update(
            use_default_hotel=(
                    config.get_param(
                        "vs_hotel_management.use_default_hotel",
                        default="False",
                    ) == "True"
            ),
            configured_hotel_id=int(
                config.get_param(
                    "vs_hotel_management.default_hotel_id",
                    default="0",
                )
            ) or False,
            use_default_building=(
                    config.get_param(
                        "vs_hotel_management.use_default_building",
                        default="False",
                    ) == "True"
            ),
            configured_building_id=int(
                config.get_param(
                    "vs_hotel_management.default_building_id",
                    default="0",
                )
            ) or False,
            use_default_floor=(
                    config.get_param(
                        "vs_hotel_management.use_default_floor",
                        default="False",
                    ) == "True"
            ),
            configured_floor_id=int(
                config.get_param(
                    "vs_hotel_management.default_floor_id",
                    default="0",
                )
            ) or False,
        )

        return res

    # ---------------------------------------------------------
    # SAVE CONFIGURATION VALUES
    # ---------------------------------------------------------

    def set_values(self):
        super().set_values()

        config = self.env["ir.config_parameter"].sudo()

        for settings in self:
            use_hotel = settings.use_default_hotel
            use_building = use_hotel and settings.use_default_building
            use_floor = use_building and settings.use_default_floor

            config.set_param(
                "vs_hotel_management.use_default_hotel",
                str(use_hotel),
            )
            config.set_param(
                "vs_hotel_management.default_hotel_id",
                settings.configured_hotel_id.id if use_hotel and settings.configured_hotel_id else "",
            )

            config.set_param(
                "vs_hotel_management.use_default_building",
                str(use_building),
            )
            config.set_param(
                "vs_hotel_management.default_building_id",
                settings.configured_building_id.id if use_building and settings.configured_building_id else "",
            )

            config.set_param(
                "vs_hotel_management.use_default_floor",
                str(use_floor),
            )
            config.set_param(
                "vs_hotel_management.default_floor_id",
                settings.configured_floor_id.id if use_floor and settings.configured_floor_id else "",
            )

    @api.onchange("use_default_hotel")
    def _onchange_use_default_hotel(self):
        if not self.use_default_hotel:
            self.use_default_building = False
            self.use_default_floor = False

    @api.onchange("use_default_building")
    def _onchange_use_default_building(self):
        if not self.use_default_building:
            self.use_default_floor = False

    @api.onchange("configured_hotel_id")
    def _onchange_configured_hotel_id(self):
        if (
                self.configured_building_id
                and self.configured_building_id.hotel_id != self.configured_hotel_id
        ):
            self.configured_building_id = False
            self.configured_floor_id = False

    @api.onchange("configured_building_id")
    def _onchange_configured_building_id(self):
        if (
                self.configured_floor_id
                and self.configured_floor_id.building_id != self.configured_building_id
        ):
            self.configured_floor_id = False