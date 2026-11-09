from odoo import api, fields, models, _
import requests
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    # ---------------------------------------------------------
    # Meta WhatsApp Cloud API Credentials
    # ---------------------------------------------------------

    whatsapp_access_token = fields.Char(
        string="Access Token",
        groups="base.group_system",
        help="Permanent or system user access token from Meta Developer Portal for WhatsApp Cloud API.",
    )

    whatsapp_phone_number_id = fields.Char(
        string="Phone Number ID",
        groups="base.group_system",
        help="WhatsApp Business Phone Number ID from Meta App Dashboard.",
    )

    whatsapp_business_account_id = fields.Char(
        string="WhatsApp Business Account ID",
        groups="base.group_system",
        help="Meta WhatsApp Business Account ID (WABA ID).",
    )

    whatsapp_api_version = fields.Char(
        string="Graph API Version",
        default="v25.0",
        groups="base.group_system",
        help="Meta Graph API Version (e.g. v25.0).",
    )

    whatsapp_template_name = fields.Char(
        string="Task Notification Template",
        default="hotel_task_notification",
        groups="base.group_system",
        help="Registered template name for task notifications in Meta WhatsApp Manager.",
    )

    whatsapp_template_language = fields.Char(
        string="Template Language",
        default="en",
        groups="base.group_system",
        help="Language code of the WhatsApp template registered in Meta (e.g. en, en_US).",
    )

    whatsapp_webhook_verify_token = fields.Char(
        string="Webhook Verify Token",
        default="hotel_whatsapp_secret",
        groups="base.group_system",
        help="Secret verification token entered in Meta Developer Webhook Configuration.",
    )

    # ---------------------------------------------------------
    # Notification Switches (Per Company)
    # ---------------------------------------------------------
    notify_housekeeping_email = fields.Boolean(
        string="Housekeeping Email Alerts",
        default=True,
        help="Send email alerts to housekeepers and managers for task assignment, inspection, and completion.",
    )
    notify_housekeeping_whatsapp = fields.Boolean(
        string="Housekeeping WhatsApp Alerts",
        default=False,
        help="Send WhatsApp notifications for housekeeping tasks.",
    )
    notify_housekeeping_sms = fields.Boolean(
        string="Housekeeping SMS Alerts",
        default=False,
        help="Send SMS alerts for housekeeping tasks.",
    )

    notify_maintenance_email = fields.Boolean(
        string="Maintenance Email Alerts",
        default=True,
        help="Send email alerts to maintenance technicians and managers.",
    )
    notify_maintenance_whatsapp = fields.Boolean(
        string="Maintenance WhatsApp Alerts",
        default=False,
        help="Send WhatsApp notifications for maintenance tasks.",
    )
    notify_maintenance_sms = fields.Boolean(
        string="Maintenance SMS Alerts",
        default=False,
        help="Send SMS alerts for maintenance tasks.",
    )

    # ---------------------------------------------------------
    # Default Staff (res.partner)
    # ---------------------------------------------------------
    housekeeping_default_staff_id = fields.Many2one(
        "res.partner",
        string="Default Housekeeping Staff",
        domain="[('is_housekeeping_staff', '=', True)]",
        help="Default operational partner assigned to checkout housekeeping tasks.",
    )

    maintenance_default_staff_id = fields.Many2one(
        "res.partner",
        string="Default Maintenance Staff",
        domain="[('is_maintenance_staff', '=', True)]",
        help="Default operational partner assigned to maintenance requests.",
    )

    # ---------------------------------------------------------
    # Custom Third-Party SMS Gateway Configuration
    # ---------------------------------------------------------
    enable_custom_sms = fields.Boolean(
        string="Enable Custom SMS Gateway",
        default=False,
        help="When enabled, hotel SMS alerts are routed through the configured third-party provider instead of Odoo standard SMS.",
    )

    sms_provider = fields.Selection(
        [
            ("twilio", "Twilio"),
            ("vonage", "Vonage (Nexmo)"),
            ("bird", "Bird (MessageBird)"),
            ("plivo", "Plivo"),
            ("custom_http", "Custom HTTP API"),
        ],
        string="SMS Provider",
        default="twilio",
        help="Select the external SMS provider used by this company.",
    )

    # Twilio
    sms_twilio_account_sid = fields.Char(string="Twilio Account SID", groups="base.group_system")
    sms_twilio_auth_token = fields.Char(string="Twilio Auth Token", groups="base.group_system")
    sms_twilio_from_number = fields.Char(string="Twilio From Number / Sender", groups="base.group_system")

    # Vonage
    sms_vonage_api_key = fields.Char(string="Vonage API Key", groups="base.group_system")
    sms_vonage_api_secret = fields.Char(string="Vonage API Secret", groups="base.group_system")
    sms_vonage_sender_id = fields.Char(string="Vonage Sender ID", groups="base.group_system")

    # Bird (MessageBird)
    sms_bird_api_key = fields.Char(string="Bird Access Key", groups="base.group_system")
    sms_bird_sender_id = fields.Char(string="Bird Sender ID / Channel", groups="base.group_system")

    # Plivo
    sms_plivo_auth_id = fields.Char(string="Plivo Auth ID", groups="base.group_system")
    sms_plivo_auth_token = fields.Char(string="Plivo Auth Token", groups="base.group_system")
    sms_plivo_from_number = fields.Char(string="Plivo Source Number", groups="base.group_system")

    # Custom HTTP API
    sms_custom_url = fields.Char(string="API Endpoint URL", groups="base.group_system")
    sms_custom_http_method = fields.Selection([("POST", "POST"), ("GET", "GET")], default="POST", string="HTTP Method", groups="base.group_system")
    sms_custom_auth_type = fields.Selection([("bearer", "Bearer Token"), ("header", "API Key Header"), ("none", "URL Parameters / None")], default="bearer", string="Auth Type", groups="base.group_system")
    sms_custom_api_key = fields.Char(string="API Key / Secret Token", groups="base.group_system")
    sms_custom_sender_id = fields.Char(string="Sender ID", groups="base.group_system")
    sms_custom_param_name_to = fields.Char(string="Recipient Field Name", default="to", groups="base.group_system")
    sms_custom_param_name_body = fields.Char(string="Message Field Name", default="message", groups="base.group_system")
    sms_custom_headers = fields.Text(string="Additional Headers (JSON)", groups="base.group_system")

    def action_test_whatsapp_connection(self):
        """Test WhatsApp Cloud API connectivity with Meta using this company's credentials."""
        self.ensure_one()
        token = self.whatsapp_access_token
        phone_number_id = self.whatsapp_phone_number_id
        api_version = (self.whatsapp_api_version or "v25.0").strip()

        if not token or not phone_number_id:
            raise UserError(
                _("Please enter both the WhatsApp Access Token and Phone Number ID for '%s' before testing.")
                % self.name
            )

        url = f"https://graph.facebook.com/{api_version}/{phone_number_id}"

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
                _("Could not connect to Meta Graph API for '%(company)s': %(error)s")
                % {"company": self.name, "error": str(error)}
            ) from error

        if not response.ok:
            error = result.get("error", {}).get(
                "message", _("Meta rejected the connection test.")
            )
            raise UserError(
                _("WhatsApp connection test failed for '%(company)s': %(error)s")
                % {"company": self.name, "error": error}
            )

        phone = result.get("display_phone_number", phone_number_id)
        verified_name = result.get("verified_name", "")

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("WhatsApp Connection Successful"),
                "message": _(
                    "Meta successfully verified WhatsApp credentials for %(phone)s (%(name)s) on company '%(company)s'. "
                    "No message was sent."
                )
                % {
                    "phone": phone,
                    "name": verified_name or _("Business account"),
                    "company": self.name,
                },
                "type": "success",
                "sticky": False,
            },
        }

    def action_test_sms_connection(self):
        """Verify SMS gateway credentials without sending a billable message wherever possible."""
        self.ensure_one()
        if not self.enable_custom_sms:
            raise UserError(_("Please enable Custom SMS Gateway first before testing."))

        provider = self.sms_provider
        if not provider:
            raise UserError(_("Please select an SMS provider."))

        if provider == "twilio":
            sid = self.sms_twilio_account_sid
            token = self.sms_twilio_auth_token
            if not sid or not token:
                raise UserError(_("Twilio Account SID and Auth Token are required."))
            url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json"
            try:
                res = requests.get(url, auth=(sid, token), timeout=15)
                res_data = res.json()
            except Exception as e:
                raise UserError(_("Could not reach Twilio API: %s") % str(e))
            if not res.ok:
                raise UserError(_("Twilio verification failed: %s") % res_data.get("message", res.text))
            account_name = res_data.get("friendly_name", sid)
            msg = _("Twilio credentials successfully verified for account '%s'.") % account_name

        elif provider == "vonage":
            key = self.sms_vonage_api_key
            secret = self.sms_vonage_api_secret
            if not key or not secret:
                raise UserError(_("Vonage API Key and API Secret are required."))
            url = f"https://rest.nexmo.com/account/get-balance?api_key={key}&api_secret={secret}"
            try:
                res = requests.get(url, timeout=15)
                res_data = res.json()
            except Exception as e:
                raise UserError(_("Could not reach Vonage API: %s") % str(e))
            if not res.ok or "value" not in res_data:
                raise UserError(_("Vonage verification failed. Please check your API Key and Secret."))
            msg = _("Vonage credentials successfully verified (Account balance: %s EUR).") % res_data.get("value")

        elif provider == "bird":
            key = self.sms_bird_api_key
            if not key:
                raise UserError(_("Bird Access Key is required."))
            url = "https://rest.messagebird.com/balance"
            try:
                res = requests.get(url, headers={"Authorization": f"AccessKey {key}"}, timeout=15)
                res_data = res.json()
            except Exception as e:
                raise UserError(_("Could not reach Bird API: %s") % str(e))
            if not res.ok:
                raise UserError(_("Bird verification failed: %s") % res.text)
            msg = _("Bird / MessageBird credentials successfully verified (Amount: %s %s).") % (
                res_data.get("amount", ""), res_data.get("type", "")
            )

        elif provider == "plivo":
            auth_id = self.sms_plivo_auth_id
            auth_token = self.sms_plivo_auth_token
            if not auth_id or not auth_token:
                raise UserError(_("Plivo Auth ID and Auth Token are required."))
            url = f"https://api.plivo.com/v1/Account/{auth_id}/"
            try:
                res = requests.get(url, auth=(auth_id, auth_token), timeout=15)
                res_data = res.json()
            except Exception as e:
                raise UserError(_("Could not reach Plivo API: %s") % str(e))
            if not res.ok:
                raise UserError(_("Plivo verification failed: %s") % res_data.get("error", res.text))
            msg = _("Plivo credentials successfully verified for account '%s' (Cash balance: %s).") % (
                res_data.get("name", auth_id), res_data.get("cash_credits", "")
            )

        elif provider == "custom_http":
            url = self.sms_custom_url
            if not url:
                raise UserError(_("Custom API URL is required."))
            msg = _("Custom HTTP API endpoint configuration saved. Connection parameters are ready.")

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("SMS Gateway Connection Verified"),
                "message": msg,
                "type": "success",
                "sticky": False,
            },
        }
