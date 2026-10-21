from odoo import fields, models, api, _
import requests
import logging
from odoo.exceptions import UserError

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

    # allow_room_add_reserved = fields.Boolean(
    #     string="Allow Adding Rooms to Reserved Reservations",
    #     config_parameter="vs_hotel_management.allow_room_add_reserved",
    #     help="Allow users to add room lines to reservations that are in the Reserved state.",
    # )

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

    auto_start_housekeeping = fields.Boolean(
        string="Automatically Start Scheduled Housekeeping",
        config_parameter="vs_hotel_management.auto_start_housekeeping",
        default=False,
    )

    auto_start_maintenance = fields.Boolean(
        string="Automatically Start Scheduled Maintenance",
        config_parameter="vs_hotel_management.auto_start_maintenance",
        default=False,
    )

    # Email notification events
    email_housekeeping_assigned = fields.Boolean(
        string="Housekeeping Assignment",
        config_parameter="vs_hotel_management.email_housekeeping_assigned",
    )
    email_housekeeping_cancelled = fields.Boolean(
        string="Housekeeping Cancellation",
        config_parameter="vs_hotel_management.email_housekeeping_cancelled",
    )
    email_maintenance_assigned = fields.Boolean(
        string="Maintenance Assignment",
        config_parameter="vs_hotel_management.email_maintenance_assigned",
    )
    email_maintenance_cancelled = fields.Boolean(
        string="Maintenance Cancellation",
        config_parameter="vs_hotel_management.email_maintenance_cancelled",
    )

    # WhatsApp notification events
    whatsapp_notifications_enabled = fields.Boolean(
        string="Enable WhatsApp Notifications",
        config_parameter="vs_hotel_management.whatsapp_enabled",
    )
    whatsapp_housekeeping_assigned = fields.Boolean(
        string="Housekeeping Assignment",
        config_parameter="vs_hotel_management.whatsapp_housekeeping_assigned",
    )
    whatsapp_housekeeping_cancelled = fields.Boolean(
        string="Housekeeping Cancellation",
        config_parameter="vs_hotel_management.whatsapp_housekeeping_cancelled",
    )
    whatsapp_maintenance_assigned = fields.Boolean(
        string="Maintenance Assignment",
        config_parameter="vs_hotel_management.whatsapp_maintenance_assigned",
    )
    whatsapp_maintenance_cancelled = fields.Boolean(
        string="Maintenance Cancellation",
        config_parameter="vs_hotel_management.whatsapp_maintenance_cancelled",
    )

    # Meta WhatsApp Cloud API credentials
    whatsapp_access_token = fields.Char(
        string="Access Token",
        config_parameter="vs_hotel_management.whatsapp_access_token",
        groups="base.group_system",
    )
    whatsapp_phone_number_id = fields.Char(
        string="Phone Number ID",
        config_parameter="vs_hotel_management.whatsapp_phone_number_id",
        groups="base.group_system",
    )
    whatsapp_business_account_id = fields.Char(
        string="WhatsApp Business Account ID",
        config_parameter="vs_hotel_management.whatsapp_business_account_id",
        groups="base.group_system",
    )
    whatsapp_api_version = fields.Char(
        string="Graph API Version",
        default="v23.0",
        config_parameter="vs_hotel_management.whatsapp_api_version",
        groups="base.group_system",
    )
    whatsapp_template_name = fields.Char(
        string="Task Notification Template",
        default="hotel_task_notification",
        config_parameter="vs_hotel_management.whatsapp_template_name",
        groups="base.group_system",
    )
    whatsapp_template_language = fields.Char(
        string="Template Language",
        default="en",
        config_parameter="vs_hotel_management.whatsapp_template_language",
        groups="base.group_system",
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

    def action_test_whatsapp_connection(self):
        self.ensure_one()

        token = self.whatsapp_access_token
        phone_number_id = self.whatsapp_phone_number_id
        api_version = (self.whatsapp_api_version or "v23.0").strip()

        if not token or not phone_number_id:
            raise UserError(
                _("Enter the WhatsApp Access Token and Phone Number ID first.")
            )

        url = (
            f"https://graph.facebook.com/{api_version}/"
            f"{phone_number_id}"
        )

        try:
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params={"fields": "display_phone_number,verified_name"},
                timeout=15,
            )
            result = response.json()
        except (requests.RequestException, ValueError) as error:
            raise UserError(
                _("Could not connect to Meta: %s") % str(error)
            ) from error

        if not response.ok:
            error = result.get("error", {}).get(
                "message", _("Meta rejected the connection test.")
            )
            raise UserError(_("Connection failed: %s") % error)

        phone = result.get("display_phone_number", phone_number_id)
        verified_name = result.get("verified_name", "")

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("WhatsApp Connection Successful"),
                "message": _(
                    "Meta accepted the credentials for %(phone)s (%(name)s). "
                    "No WhatsApp message was sent."
                ) % {
                               "phone": phone,
                               "name": verified_name or _("Business account"),
                           },
                "type": "success",
                "sticky": False,
            },
        }