from odoo import fields, models, api, _
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ---------------------------------------------------------
    # General & Timing
    # ---------------------------------------------------------

    checkin_time_default = fields.Float(
        string="Default Check-in Time",
        config_parameter="vs_hotel_management.checkin_time_default",
        default=14.0,
        help="Standard default check-in time in 24-hour format (e.g. 14.0 for 2:00 PM). Used when creating new reservations.",
    )

    checkout_time_default = fields.Float(
        string="Default Check-out Time",
        config_parameter="vs_hotel_management.checkout_time_default",
        default=12.0,
        help="Standard default check-out time in 24-hour format (e.g. 12.0 for 12:00 PM noon). Used when creating new reservations.",
    )

    allow_overbooking = fields.Boolean(
        string="Allow Overbooking",
        config_parameter="vs_hotel_management.allow_overbooking",
        help="Allow reservations to exceed room availability without throwing blocking errors.",
    )

    allow_early_checkin = fields.Boolean(
        string="Allow Early Check-in",
        config_parameter="vs_hotel_management.allow_early_checkin",
        help="Allow front desk users to check in guests before the scheduled check-in time.",
    )

    allow_early_checkout = fields.Boolean(
        string="Allow Early Checkout",
        config_parameter="vs_hotel_management.allow_early_checkout",
        help="Allow checkout before the scheduled checkout time without requiring special authorization.",
    )

    mark_room_dirty_on_checkout = fields.Boolean(
        string="Mark Room Dirty on Checkout",
        config_parameter="vs_hotel_management.mark_room_dirty_on_checkout",
        help="Automatically change room status to Dirty and generate a checkout housekeeping task when a guest checks out.",
    )

    # ---------------------------------------------------------
    # Reservation Automation & Billing
    # ---------------------------------------------------------

    hotel_auto_confirm_reservation = fields.Boolean(
        string="Auto-confirm Reservations",
        default=False,
        config_parameter="vs_hotel_management.auto_confirm_reservation",
        help="Automatically confirm newly created hotel reservations upon saving.",
    )

    hotel_auto_create_invoice = fields.Boolean(
        string="Auto-create Invoice",
        default=False,
        config_parameter="vs_hotel_management.auto_create_invoice",
        help="Automatically generate a customer invoice from the guest folio upon guest checkout.",
    )

    hotel_require_payment_before_checkout = fields.Boolean(
        string="Require Payment Before Checkout",
        default=False,
        config_parameter="vs_hotel_management.require_payment_before_checkout",
        help="Enforce full payment and zero outstanding balance on the guest folio before checkout can be performed.",
    )

    hotel_auto_close_folio_after_payment = fields.Boolean(
        string="Auto-close Folio After Payment",
        default=True,
        config_parameter="vs_hotel_management.auto_close_folio_after_payment",
        help="Automatically change the guest folio status to Closed once all payments have been received.",
    )

    # ---------------------------------------------------------
    # Room & Task Automation
    # ---------------------------------------------------------

    auto_start_housekeeping = fields.Boolean(
        string="Automatically Start Scheduled Housekeeping",
        config_parameter="vs_hotel_management.auto_start_housekeeping",
        default=False,
        help="Automatically start scheduled housekeeping tasks when their scheduled time is reached via cron.",
    )

    auto_start_maintenance = fields.Boolean(
        string="Automatically Start Scheduled Maintenance",
        config_parameter="vs_hotel_management.auto_start_maintenance",
        default=False,
        help="Automatically start scheduled maintenance tasks when their scheduled time is reached via cron.",
    )

    housekeeping_assigned_user_id = fields.Many2one(
        "res.users",
        string="Assigned Housekeeper",
        domain="[('share', '=', False)]",
        help="Housekeeping staff member automatically assigned to checkout cleaning tasks when room automation is enabled.",
    )

    # ---------------------------------------------------------
    # Reservation Rules & Policies
    # ---------------------------------------------------------

    hotel_require_guest = fields.Boolean(
        string="Require Guest",
        default=True,
        config_parameter="vs_hotel_management.require_guest",
        help="Require a selected guest partner on the reservation before confirming.",
    )

    hotel_require_rate_plan = fields.Boolean(
        string="Require Rate Plan",
        default=True,
        config_parameter="vs_hotel_management.require_rate_plan",
        help="Require a rate plan to be selected on each reservation room line.",
    )

    hotel_minimum_stay = fields.Integer(
        string="Minimum Stay (Nights)",
        default=1,
        config_parameter="vs_hotel_management.minimum_stay",
        help="Minimum number of nights required for any reservation.",
    )

    hotel_maximum_stay = fields.Integer(
        string="Maximum Stay (Nights)",
        default=365,
        config_parameter="vs_hotel_management.maximum_stay",
        help="Maximum number of nights allowed for a reservation.",
    )

    # ---------------------------------------------------------
    # Default Property Hierarchy
    # ---------------------------------------------------------

    use_default_hotel = fields.Boolean(
        string="Use Default Hotel",
        help="Pre-populate the selected default hotel on new reservations and room forms.",
    )

    configured_hotel_id = fields.Many2one(
        "hotel.hotel",
        string="Default Hotel",
        help="The default hotel pre-selected when creating new reservations.",
    )

    use_default_building = fields.Boolean(
        string="Use Default Building",
        help="Pre-populate the selected default building on new rooms and reservations.",
    )

    configured_building_id = fields.Many2one(
        "hotel.building",
        string="Default Building",
        domain="[('hotel_id', '=', configured_hotel_id)]",
        help="The default building pre-selected when creating new rooms.",
    )

    use_default_floor = fields.Boolean(
        string="Use Default Floor",
        help="Pre-populate the selected default floor on new rooms.",
    )

    configured_floor_id = fields.Many2one(
        "hotel.building.floor",
        string="Default Floor",
        domain="[('building_id', '=', configured_building_id)]",
        help="The default floor pre-selected when creating new rooms.",
    )

    # ---------------------------------------------------------
    # Master Channel Controls
    # ---------------------------------------------------------

    email_notifications_enabled = fields.Boolean(
        string="Enable Email Notifications",
        config_parameter="vs_hotel_management.email_enabled",
        default=True,
        help="Master switch to activate or deactivate automated email notifications across all hotel workflows.",
    )

    whatsapp_notifications_enabled = fields.Boolean(
        string="Enable WhatsApp Notifications",
        config_parameter="vs_hotel_management.whatsapp_enabled",
        default=False,
        help="Master switch to activate or deactivate automated Meta WhatsApp notifications across all hotel workflows.",
    )

    sms_notifications_enabled = fields.Boolean(
        string="Enable SMS Notifications",
        config_parameter="vs_hotel_management.sms_enabled",
        default=False,
        help="Master switch to activate or deactivate automated SMS notifications across hotel workflows.",
    )

    # ---------------------------------------------------------
    # Reservation Notifications (Email, WhatsApp & SMS)
    # ---------------------------------------------------------

    email_reservation_confirmed = fields.Boolean(
        string="Email on Confirmation",
        config_parameter="vs_hotel_management.email_reservation_confirmed",
        default=True,
        help="Send an automatic reservation confirmation email with full booking details to the guest.",
    )

    email_reservation_cancelled = fields.Boolean(
        string="Email on Cancellation",
        config_parameter="vs_hotel_management.email_reservation_cancelled",
        default=True,
        help="Send an automatic cancellation notice email to the guest when a reservation is cancelled.",
    )

    email_reservation_checkout = fields.Boolean(
        string="Email on Checkout (Thank You & Folio)",
        config_parameter="vs_hotel_management.email_reservation_checkout",
        default=True,
        help="Send an automatic thank-you email including folio charges and billing statement to the guest upon checkout.",
    )

    email_reservation_noshow = fields.Boolean(
        string="Email on No-Show",
        config_parameter="vs_hotel_management.email_reservation_noshow",
        default=False,
        help="Send an automatic notification email to the guest when their reservation is marked as No-Show.",
    )

    whatsapp_reservation_confirmed = fields.Boolean(
        string="WhatsApp on Confirmation",
        config_parameter="vs_hotel_management.whatsapp_reservation_confirmed",
        default=False,
        help="Send an automatic WhatsApp confirmation message with booking summary to the guest's phone number.",
    )

    whatsapp_reservation_cancelled = fields.Boolean(
        string="WhatsApp on Cancellation",
        config_parameter="vs_hotel_management.whatsapp_reservation_cancelled",
        default=False,
        help="Send an automatic WhatsApp cancellation notification to the guest when a reservation is cancelled.",
    )

    whatsapp_reservation_checkout = fields.Boolean(
        string="WhatsApp on Checkout (Thank You & Folio)",
        config_parameter="vs_hotel_management.whatsapp_reservation_checkout",
        default=False,
        help="Send an automatic WhatsApp thank-you message with folio charges, payments, and balance upon checkout.",
    )

    whatsapp_reservation_noshow = fields.Boolean(
        string="WhatsApp on No-Show",
        config_parameter="vs_hotel_management.whatsapp_reservation_noshow",
        default=False,
        help="Send an automatic WhatsApp notice to the guest when their reservation is marked as No-Show.",
    )

    sms_reservation_confirmed = fields.Boolean(
        string="SMS on Confirmation",
        config_parameter="vs_hotel_management.sms_reservation_confirmed",
        default=False,
        help="Send an automatic SMS confirmation alert to the guest when a reservation is confirmed.",
    )

    sms_reservation_cancelled = fields.Boolean(
        string="SMS on Cancellation",
        config_parameter="vs_hotel_management.sms_reservation_cancelled",
        default=False,
        help="Send an automatic SMS cancellation alert to the guest when a reservation is cancelled.",
    )

    sms_reservation_checkout = fields.Boolean(
        string="SMS on Checkout",
        config_parameter="vs_hotel_management.sms_reservation_checkout",
        default=False,
        help="Send an automatic SMS thank-you notification with folio balance upon checkout.",
    )

    sms_reservation_noshow = fields.Boolean(
        string="SMS on No-Show",
        config_parameter="vs_hotel_management.sms_reservation_noshow",
        default=False,
        help="Send an automatic SMS alert to the guest when their reservation is marked as No-Show.",
    )

    # ---------------------------------------------------------
    # Task Notifications (Housekeeping & Maintenance)
    # ---------------------------------------------------------

    email_housekeeping_assigned = fields.Boolean(
        string="Housekeeping Assignment (Email)",
        config_parameter="vs_hotel_management.email_housekeeping_assigned",
        default=True,
        help="Send an email to the assigned housekeeper when a task is assigned.",
    )

    email_housekeeping_cancelled = fields.Boolean(
        string="Housekeeping Cancellation (Email)",
        config_parameter="vs_hotel_management.email_housekeeping_cancelled",
        default=False,
        help="Send an email cancellation notice to the housekeeper if the task is cancelled.",
    )

    email_maintenance_assigned = fields.Boolean(
        string="Maintenance Assignment (Email)",
        config_parameter="vs_hotel_management.email_maintenance_assigned",
        default=True,
        help="Send an email to the assigned technician when a maintenance task is assigned.",
    )

    email_maintenance_cancelled = fields.Boolean(
        string="Maintenance Cancellation (Email)",
        config_parameter="vs_hotel_management.email_maintenance_cancelled",
        default=False,
        help="Send an email cancellation notice to the technician if the maintenance task is cancelled.",
    )

    whatsapp_housekeeping_assigned = fields.Boolean(
        string="Housekeeping Assignment (WhatsApp)",
        config_parameter="vs_hotel_management.whatsapp_housekeeping_assigned",
        default=False,
        help="Send a WhatsApp notification to the assigned housekeeper when a task is assigned.",
    )

    whatsapp_housekeeping_cancelled = fields.Boolean(
        string="Housekeeping Cancellation (WhatsApp)",
        config_parameter="vs_hotel_management.whatsapp_housekeeping_cancelled",
        default=False,
        help="Send a WhatsApp cancellation notice to the housekeeper if the task is cancelled.",
    )

    whatsapp_maintenance_assigned = fields.Boolean(
        string="Maintenance Assignment (WhatsApp)",
        config_parameter="vs_hotel_management.whatsapp_maintenance_assigned",
        default=False,
        help="Send a WhatsApp notification to the assigned technician when a maintenance task is assigned.",
    )

    whatsapp_maintenance_cancelled = fields.Boolean(
        string="Maintenance Cancellation (WhatsApp)",
        config_parameter="vs_hotel_management.whatsapp_maintenance_cancelled",
        default=False,
        help="Send a WhatsApp cancellation notice to the technician if the maintenance task is cancelled.",
    )

    sms_housekeeping_assigned = fields.Boolean(
        string="Housekeeping Assignment (SMS)",
        config_parameter="vs_hotel_management.sms_housekeeping_assigned",
        default=False,
        help="Send an SMS alert to the assigned housekeeper when a task is assigned.",
    )

    sms_maintenance_assigned = fields.Boolean(
        string="Maintenance Assignment (SMS)",
        config_parameter="vs_hotel_management.sms_maintenance_assigned",
        default=False,
        help="Send an SMS alert to the assigned technician when a maintenance task is assigned.",
    )

    # ---------------------------------------------------------
    # Company-based Meta WhatsApp Cloud API Credentials
    # ---------------------------------------------------------

    whatsapp_access_token = fields.Char(
        related="company_id.whatsapp_access_token",
        readonly=False,
        string="Access Token",
        groups="base.group_system",
        help="Meta WhatsApp Cloud API permanent or system user access token for this company.",
    )

    whatsapp_phone_number_id = fields.Char(
        related="company_id.whatsapp_phone_number_id",
        readonly=False,
        string="Phone Number ID",
        groups="base.group_system",
        help="WhatsApp Business Phone Number ID from Meta App Dashboard for this company.",
    )

    whatsapp_business_account_id = fields.Char(
        related="company_id.whatsapp_business_account_id",
        readonly=False,
        string="WhatsApp Business Account ID",
        groups="base.group_system",
        help="Meta WhatsApp Business Account ID (WABA ID) for this company.",
    )

    whatsapp_api_version = fields.Char(
        related="company_id.whatsapp_api_version",
        readonly=False,
        string="Graph API Version",
        groups="base.group_system",
        help="Meta Graph API version (e.g. v23.0) for this company.",
    )

    whatsapp_template_name = fields.Char(
        related="company_id.whatsapp_template_name",
        readonly=False,
        string="Task Notification Template",
        groups="base.group_system",
        help="Default registered template name for task notifications in Meta WhatsApp Manager.",
    )

    whatsapp_template_language = fields.Char(
        related="company_id.whatsapp_template_language",
        readonly=False,
        string="Template Language",
        groups="base.group_system",
        help="Language code of the WhatsApp template registered in Meta (e.g., en, en_US).",
    )

    whatsapp_webhook_verify_token = fields.Char(
        related="company_id.whatsapp_webhook_verify_token",
        readonly=False,
        string="Webhook Verify Token",
        groups="base.group_system",
        help="Secret verification token entered in Meta Developer Webhook Configuration.",
    )

    whatsapp_webhook_url = fields.Char(
        string="Webhook Callback URL",
        compute="_compute_whatsapp_webhook_url",
        help="Configure this URL in Meta Developer Portal > WhatsApp > Configuration > Callback URL.",
    )

    def _compute_whatsapp_webhook_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url", "http://localhost:8069"
        ).rstrip("/")
        for rec in self:
            rec.whatsapp_webhook_url = f"{base_url}/hotel/whatsapp/webhook"

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
            housekeeping_assigned_user_id=int(
                config.get_param(
                    "vs_hotel_management.housekeeping_assigned_user_id",
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

            config.set_param(
                "vs_hotel_management.housekeeping_assigned_user_id",
                settings.housekeeping_assigned_user_id.id if settings.housekeeping_assigned_user_id else "",
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

    @api.onchange("mark_room_dirty_on_checkout")
    def _onchange_mark_room_dirty_on_checkout(self):
        if not self.mark_room_dirty_on_checkout:
            self.auto_start_housekeeping = False
            self.auto_start_maintenance = False
            self.housekeeping_assigned_user_id = False

    @api.onchange("auto_start_housekeeping")
    def _onchange_auto_start_housekeeping(self):
        if not self.auto_start_housekeeping:
            self.housekeeping_assigned_user_id = False

    def action_test_whatsapp_connection(self):
        """Test Meta WhatsApp Cloud API connection using the active company's credentials."""
        self.ensure_one()
        if not self.company_id:
            raise UserError(_("Please select a company before testing the WhatsApp connection."))
        return self.company_id.action_test_whatsapp_connection()