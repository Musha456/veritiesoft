# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class HotelSmsService(models.AbstractModel):
    """
    Centralized Multi-Provider SMS Service for Hotel Management System.
    Supports Twilio, Vonage, Bird, Plivo, and Custom HTTP APIs with company isolation.
    """
    _name = "hotel.sms.service"
    _description = "Hotel SMS Service Dispatcher"

    @api.model
    def send_sms(self, to_number, body, company=None):
        """
        Centralized SMS dispatch method.
        - If custom SMS is disabled: uses standard Odoo SMS infrastructure (sms.sms).
        - If custom SMS is enabled: calls the configured provider adapter.
        - Never silently falls back to Odoo SMS on custom provider failure.
        """
        company = company or self.env.company
        if not to_number or not body:
            _logger.warning("SMS send skipped: missing recipient number or message body.")
            return False

        clean_number = "".join(c for c in str(to_number) if c.isdigit() or c == "+")
        if not clean_number:
            _logger.warning("SMS send skipped: invalid phone number '%s'.", to_number)
            return False

        # Mode 1: Standard Odoo SMS
        if not company.enable_custom_sms:
            return self._send_standard_odoo_sms(clean_number, body)

        # Mode 2: Custom SMS Gateway
        provider = company.sms_provider
        if not provider:
            raise UserError(_("Custom SMS is enabled for '%s', but no SMS provider is selected.") % company.name)

        _logger.info("Dispatching custom SMS to %s via %s (Company: %s)", clean_number, provider, company.name)

        if provider == "twilio":
            return self._send_twilio(company, clean_number, body)
        elif provider == "vonage":
            return self._send_vonage(company, clean_number, body)
        elif provider == "bird":
            return self._send_bird(company, clean_number, body)
        elif provider == "plivo":
            return self._send_plivo(company, clean_number, body)
        elif provider == "custom_http":
            return self._send_custom_http(company, clean_number, body)
        else:
            raise UserError(_("Unsupported SMS provider '%s'.") % provider)

    @api.model
    def _send_standard_odoo_sms(self, to_number, body):
        """Send via Odoo standard SMS engine."""
        if "sms.sms" in self.env:
            try:
                sms = self.env["sms.sms"].sudo().create({
                    "number": to_number,
                    "body": body,
                })
                sms.send()
                _logger.info("Sent standard Odoo SMS to %s", to_number)
                return True
            except Exception as e:
                _logger.warning("Standard Odoo SMS delivery failed for %s: %s", to_number, e)
                return False
        _logger.info("Standard SMS module not installed; logged SMS to %s: %s", to_number, body[:80])
        return True

    # ---------------------------------------------------------
    # Provider 1: Twilio
    # ---------------------------------------------------------
    @api.model
    def _send_twilio(self, company, to_number, body):
        account_sid = company.sms_twilio_account_sid
        auth_token = company.sms_twilio_auth_token
        from_number = company.sms_twilio_from_number

        if not account_sid or not auth_token or not from_number:
            raise UserError(_("Twilio configuration is incomplete for company '%s'.") % company.name)

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        data = {
            "From": from_number,
            "To": to_number,
            "Body": body,
        }
        try:
            response = requests.post(
                url,
                data=data,
                auth=(account_sid, auth_token),
                timeout=15,
            )
            res_json = response.json()
        except Exception as e:
            _logger.error("Twilio SMS network error for %s: %s", to_number, str(e))
            raise UserError(_("Twilio SMS transmission failed: %s") % str(e))

        if not response.ok:
            error_msg = res_json.get("message", response.text)
            _logger.error("Twilio SMS error (%s): %s", response.status_code, error_msg)
            raise UserError(_("Twilio error: %s") % error_msg)

        _logger.info("Twilio SMS sent successfully to %s (SID: %s)", to_number, res_json.get("sid"))
        return True

    # ---------------------------------------------------------
    # Provider 2: Vonage (Nexmo)
    # ---------------------------------------------------------
    @api.model
    def _send_vonage(self, company, to_number, body):
        api_key = company.sms_vonage_api_key
        api_secret = company.sms_vonage_api_secret
        from_sender = company.sms_vonage_sender_id or company.name[:11]

        if not api_key or not api_secret:
            raise UserError(_("Vonage credentials missing for company '%s'.") % company.name)

        clean_to = to_number.lstrip("+")
        url = "https://rest.nexmo.com/sms/json"
        payload = {
            "api_key": api_key,
            "api_secret": api_secret,
            "to": clean_to,
            "from": from_sender,
            "text": body,
        }
        try:
            response = requests.post(url, json=payload, timeout=15)
            res_json = response.json()
        except Exception as e:
            _logger.error("Vonage SMS network error for %s: %s", to_number, str(e))
            raise UserError(_("Vonage SMS transmission failed: %s") % str(e))

        messages = res_json.get("messages", [])
        if messages and messages[0].get("status") != "0":
            err = messages[0].get("error-text", "Delivery rejected by Vonage")
            _logger.error("Vonage SMS error: %s", err)
            raise UserError(_("Vonage error: %s") % err)

        _logger.info("Vonage SMS sent successfully to %s", to_number)
        return True

    # ---------------------------------------------------------
    # Provider 3: Bird (MessageBird)
    # ---------------------------------------------------------
    @api.model
    def _send_bird(self, company, to_number, body):
        api_key = company.sms_bird_api_key
        originator = company.sms_bird_sender_id or company.name[:11]

        if not api_key:
            raise UserError(_("Bird / MessageBird Access Key is missing for company '%s'.") % company.name)

        url = "https://rest.messagebird.com/messages"
        headers = {
            "Authorization": f"AccessKey {api_key}",
            "Content-Type": "application/json",
        }
        clean_to = to_number.lstrip("+")
        payload = {
            "originator": originator,
            "recipients": [clean_to],
            "body": body,
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            res_json = response.json()
        except Exception as e:
            _logger.error("Bird SMS network error: %s", str(e))
            raise UserError(_("Bird SMS transmission failed: %s") % str(e))

        if not response.ok:
            errors = res_json.get("errors", [{}])
            err_desc = errors[0].get("description", response.text)
            _logger.error("Bird SMS error: %s", err_desc)
            raise UserError(_("Bird SMS error: %s") % err_desc)

        _logger.info("Bird SMS sent successfully to %s", to_number)
        return True

    # ---------------------------------------------------------
    # Provider 4: Plivo
    # ---------------------------------------------------------
    @api.model
    def _send_plivo(self, company, to_number, body):
        auth_id = company.sms_plivo_auth_id
        auth_token = company.sms_plivo_auth_token
        source_number = company.sms_plivo_from_number

        if not auth_id or not auth_token or not source_number:
            raise UserError(_("Plivo credentials missing for company '%s'.") % company.name)

        clean_to = to_number.lstrip("+")
        url = f"https://api.plivo.com/v1/Account/{auth_id}/Message/"
        payload = {
            "src": source_number,
            "dst": clean_to,
            "text": body,
        }
        try:
            response = requests.post(
                url,
                json=payload,
                auth=(auth_id, auth_token),
                timeout=15,
            )
            res_json = response.json()
        except Exception as e:
            _logger.error("Plivo SMS network error: %s", str(e))
            raise UserError(_("Plivo SMS transmission failed: %s") % str(e))

        if not response.ok:
            err = res_json.get("error", response.text)
            _logger.error("Plivo SMS error: %s", err)
            raise UserError(_("Plivo error: %s") % err)

        _logger.info("Plivo SMS sent successfully to %s", to_number)
        return True

    # ---------------------------------------------------------
    # Provider 5: Custom HTTP API
    # ---------------------------------------------------------
    @api.model
    def _send_custom_http(self, company, to_number, body):
        url = company.sms_custom_url
        method = (company.sms_custom_http_method or "POST").upper()
        auth_type = company.sms_custom_auth_type or "bearer"
        token = company.sms_custom_api_key or ""
        sender_id = company.sms_custom_sender_id or ""
        param_to = company.sms_custom_param_name_to or "to"
        param_body = company.sms_custom_param_name_body or "message"

        if not url:
            raise UserError(_("Custom SMS HTTP API URL is missing for company '%s'.") % company.name)

        headers = {"User-Agent": "Odoo20-Hotel-SMS/1.0"}
        if company.sms_custom_headers:
            try:
                custom_hdr = json.loads(company.sms_custom_headers)
                if isinstance(custom_hdr, dict):
                    headers.update(custom_hdr)
            except Exception:
                pass

        if auth_type == "bearer" and token:
            headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "header" and token:
            headers["X-API-KEY"] = token

        payload = {
            param_to: to_number,
            param_body: body,
        }
        if sender_id:
            payload["from"] = sender_id

        try:
            if method == "GET":
                response = requests.get(url, params=payload, headers=headers, timeout=15)
            else:
                response = requests.post(url, json=payload, headers=headers, timeout=15)
        except Exception as e:
            _logger.error("Custom SMS API error: %s", str(e))
            raise UserError(_("Custom SMS Gateway error: %s") % str(e))

        if not response.ok:
            _logger.error("Custom SMS API rejected message with HTTP %s: %s", response.status_code, response.text[:200])
            raise UserError(_("Custom SMS Gateway returned HTTP %s") % response.status_code)

        _logger.info("Custom HTTP SMS sent successfully to %s", to_number)
        return True
