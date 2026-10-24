import json
import logging
from odoo import http, fields, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class WhatsAppWebhookController(http.Controller):

    @http.route(
        ["/hotel/whatsapp/webhook"],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def whatsapp_webhook_verify(self, **kwargs):
        """
        Meta Webhook verification endpoint (GET).
        Responds to Meta verification challenge when setting up or verifying the callback URL.
        """
        mode = kwargs.get("hub.mode") or request.params.get("hub.mode")
        challenge = kwargs.get("hub.challenge") or request.params.get("hub.challenge")
        verify_token = kwargs.get("hub.verify_token") or request.params.get("hub.verify_token")

        _logger.info("Meta WhatsApp Webhook verification request received: mode=%s, token=%s", mode, verify_token)

        if mode == "subscribe" and verify_token:
            # Check against configured company verify tokens or default fallback
            companies = request.env["res.company"].sudo().search([])
            valid_tokens = set(companies.mapped("whatsapp_webhook_verify_token"))
            default_token = request.env["ir.config_parameter"].sudo().get_param(
                "vs_hotel_management.whatsapp_webhook_verify_token", "hotel_whatsapp_secret"
            )
            valid_tokens.add(default_token)
            valid_tokens.add("hotel_whatsapp_secret")
            valid_tokens = {t for t in valid_tokens if t}

            if verify_token in valid_tokens:
                _logger.info("Meta WhatsApp Webhook verified successfully with challenge: %s", challenge)
                return request.make_response(str(challenge), headers=[("Content-Type", "text/plain")])

        _logger.warning("Meta WhatsApp Webhook verification failed. Invalid token '%s'", verify_token)
        return request.make_response("Forbidden", headers=[("Content-Type", "text/plain")], status=403)

    @http.route(
        ["/hotel/whatsapp/webhook"],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def whatsapp_webhook_post(self, **kwargs):
        """
        Meta Webhook event delivery endpoint (POST).
        Receives delivery receipts, read receipts, and asynchronous failure statuses from Meta Cloud API.
        """
        raw_body = request.httprequest.data
        if not raw_body:
            return request.make_response("NO_DATA", headers=[("Content-Type", "text/plain")])

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            _logger.error("Failed to parse WhatsApp Webhook JSON payload: %s", e)
            return request.make_response("INVALID_JSON", headers=[("Content-Type", "text/plain")], status=400)

        _logger.info("Meta WhatsApp Webhook event payload received: %s", payload)

        entries = payload.get("entry", [])
        WhatsAppLog = request.env["hotel.whatsapp.log"].sudo()

        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                statuses = value.get("statuses", [])
                for status_item in statuses:
                    try:
                        WhatsAppLog._process_webhook_status(status_item)
                    except Exception as exc:
                        _logger.exception("Error processing WhatsApp status update %s: %s", status_item, exc)

        return request.make_response("EVENT_RECEIVED", headers=[("Content-Type", "text/plain")])
