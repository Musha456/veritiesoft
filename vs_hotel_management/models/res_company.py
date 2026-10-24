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
        default="v23.0",
        groups="base.group_system",
        help="Meta Graph API Version (e.g. v23.0).",
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

    def action_test_whatsapp_connection(self):
        """Test WhatsApp Cloud API connectivity with Meta using this company's credentials."""
        self.ensure_one()
        token = self.whatsapp_access_token
        phone_number_id = self.whatsapp_phone_number_id
        api_version = (self.whatsapp_api_version or "v23.0").strip()

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
