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
    # Simplified Notification Channels & Automation
    # ---------------------------------------------------------

    # 1. Reservation Notifications (Email, WhatsApp, SMS)
    notify_reservation_email = fields.Boolean(
        string="Send Email for Reservation Actions",
        config_parameter="vs_hotel_management.notify_reservation_email",
        default=True,
        help="Automatically send email notifications to guests for all reservation lifecycle actions (confirmation, cancellation, checkout, no-show).",
    )

    notify_reservation_whatsapp = fields.Boolean(
        string="Send WhatsApp for Reservation Actions",
        config_parameter="vs_hotel_management.notify_reservation_whatsapp",
        default=False,
        help="Automatically send Meta WhatsApp messages to guests for all reservation lifecycle actions (confirmation, cancellation, checkout, no-show).",
    )

    notify_reservation_sms = fields.Boolean(
        string="Send SMS for Reservation Actions",
        config_parameter="vs_hotel_management.notify_reservation_sms",
        default=False,
        help="Automatically send SMS alerts to guests for all reservation lifecycle actions (confirmation, cancellation, checkout, no-show).",
    )

    # 2. Housekeeping Task Notifications (Email, WhatsApp, SMS)
    notify_housekeeping_email = fields.Boolean(
        string="Send Email for Housekeeping Tasks",
        config_parameter="vs_hotel_management.notify_housekeeping_email",
        default=True,
        help="Send email notifications to assigned housekeepers for task assignment and cancellation.",
    )

    notify_housekeeping_whatsapp = fields.Boolean(
        string="Send WhatsApp for Housekeeping Tasks",
        config_parameter="vs_hotel_management.notify_housekeeping_whatsapp",
        default=False,
        help="Send WhatsApp messages to assigned housekeepers for task assignment and cancellation.",
    )

    notify_housekeeping_sms = fields.Boolean(
        string="Send SMS for Housekeeping Tasks",
        config_parameter="vs_hotel_management.notify_housekeeping_sms",
        default=False,
        help="Send SMS alerts to assigned housekeepers for task assignment and cancellation.",
    )

    # 3. Maintenance Task Notifications (Email, WhatsApp, SMS)
    notify_maintenance_email = fields.Boolean(
        string="Send Email for Maintenance Tasks",
        config_parameter="vs_hotel_management.notify_maintenance_email",
        default=True,
        help="Send email notifications to assigned technicians for maintenance task assignment and cancellation.",
    )

    notify_maintenance_whatsapp = fields.Boolean(
        string="Send WhatsApp for Maintenance Tasks",
        config_parameter="vs_hotel_management.notify_maintenance_whatsapp",
        default=False,
        help="Send WhatsApp messages to assigned technicians for maintenance task assignment and cancellation.",
    )

    notify_maintenance_sms = fields.Boolean(
        string="Send SMS for Maintenance Tasks",
        config_parameter="vs_hotel_management.notify_maintenance_sms",
        default=False,
        help="Send SMS alerts to assigned technicians for maintenance task assignment and cancellation.",
    )

    # ---------------------------------------------------------
    # Travel Agent Commission Configuration
    # ---------------------------------------------------------

    enable_travel_agent_commission = fields.Boolean(
        string="Enable Travel Agent Commission",
        config_parameter="vs_hotel_management.enable_travel_agent_commission",
        default=False,
        help="Enable travel agent commission calculation on reservations.",
    )

    hotel_default_agent_commission_percentage = fields.Float(
        string="Default Commission (%)",
        config_parameter="vs_hotel_management.default_agent_commission_percentage",
        default=10.0,
        help="Default commission percentage applied to travel agents when not set on their contact profile.",
    )

    # ---------------------------------------------------------
    # Rate Plan & Discounts Defaults
    # ---------------------------------------------------------

    hotel_default_rate_plan_id = fields.Many2one(
        "hotel.rate.plan",
        string="Default Rate Plan",
        help="Default rate plan pre-selected on reservation room lines.",
    )

    hotel_default_room_discount_id = fields.Many2one(
        "hotel.discount",
        string="Default Room Discount",
        domain="[('state', '=', 'active')]",
        help="Default discount pre-selected for room bookings.",
    )

    hotel_default_service_discount_id = fields.Many2one(
        "hotel.discount",
        string="Default Service Discount",
        domain="[('state', '=', 'active')]",
        help="Default discount pre-selected for hotel service lines.",
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
        help="Meta Graph API version (e.g. v25.0) for this company.",
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

        def get_config_id(key):
            value = config.get_param(key, default="0")
            return int(value) if value and value.isdigit() and int(value) > 0 else False

        res.update(
            use_default_hotel=(
                    config.get_param(
                        "vs_hotel_management.use_default_hotel",
                        default="False",
                    ) == "True"
            ),
            configured_hotel_id=get_config_id(
                "vs_hotel_management.default_hotel_id"
            ),
            use_default_building=(
                    config.get_param(
                        "vs_hotel_management.use_default_building",
                        default="False",
                    ) == "True"
            ),
            configured_building_id=get_config_id(
                "vs_hotel_management.default_building_id"
            ),
            use_default_floor=(
                    config.get_param(   
                        "vs_hotel_management.use_default_floor",
                        default="False",
                    ) == "True"
            ),
            configured_floor_id=get_config_id(
                "vs_hotel_management.default_floor_id"
            ),
            housekeeping_assigned_user_id=get_config_id(
                "vs_hotel_management.housekeeping_assigned_user_id"
            ),
            hotel_default_rate_plan_id=get_config_id(
                "vs_hotel_management.default_rate_plan_id"
            ),
            hotel_default_room_discount_id=get_config_id(
                "vs_hotel_management.default_room_discount_id"
            ),
            hotel_default_service_discount_id=get_config_id(
                "vs_hotel_management.default_service_discount_id"
            ),
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
            config.set_param(
                "vs_hotel_management.default_rate_plan_id",
                settings.hotel_default_rate_plan_id.id if settings.hotel_default_rate_plan_id else "",
            )
            config.set_param(
                "vs_hotel_management.default_room_discount_id",
                settings.hotel_default_room_discount_id.id if settings.hotel_default_room_discount_id else "",
            )
            config.set_param(
                "vs_hotel_management.default_service_discount_id",
                settings.hotel_default_service_discount_id.id if settings.hotel_default_service_discount_id else "",
            )

            # Synchronize master notification channel switches with modular settings
            whatsapp_active = bool(
                settings.notify_reservation_whatsapp
                or settings.notify_housekeeping_whatsapp
                or settings.notify_maintenance_whatsapp
            )
            config.set_param("vs_hotel_management.whatsapp_enabled", str(whatsapp_active))

            email_active = bool(
                settings.notify_reservation_email
                or settings.notify_housekeeping_email
                or settings.notify_maintenance_email
            )
            config.set_param("vs_hotel_management.email_enabled", str(email_active))

            sms_active = bool(
                settings.notify_reservation_sms
                or settings.notify_housekeeping_sms
                or settings.notify_maintenance_sms
            )
            config.set_param("vs_hotel_management.sms_enabled", str(sms_active))

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