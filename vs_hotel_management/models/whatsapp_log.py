from odoo import api, fields, models, tools, _
from odoo.tools import config
import requests
import logging
import datetime
from markupsafe import Markup, escape
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HotelWhatsAppLog(models.Model):
    _name = "hotel.whatsapp.log"
    _description = "Hotel WhatsApp Notification Log"
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        readonly=True,
        default="New",
        copy=False,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        readonly=True,
        index=True,
    )
    recipient_id = fields.Many2one(
        "res.partner",
        string="Recipient",
        index=True,
    )
    phone_number = fields.Char(
        string="WhatsApp Number",
        index=True,
    )
    task_type = fields.Selection(
        [
            ("housekeeping", "Housekeeping"),
            ("maintenance", "Maintenance"),
            ("reservation", "Reservation"),
            ("folio", "Folio"),
            ("other", "Other"),
        ],
        string="Module / Type",
        required=True,
        readonly=True,
        default="other",
        index=True,
    )
    event = fields.Selection(
        [
            ("assigned", "Assigned"),
            ("cancelled", "Cancelled"),
            ("confirmed", "Confirmed"),
            ("checkout", "Checked Out"),
            ("no_show", "No Show"),
            ("other", "Other"),
        ],
        string="Event",
        required=True,
        readonly=True,
    )
    task_reference = fields.Reference(
        selection=[
            ("hotel.housekeeping", "Housekeeping Task"),
            ("hotel.maintenance", "Maintenance Task"),
            ("hotel.reservation", "Reservation"),
            ("hotel.guest.folio", "Guest Folio"),
        ],
        string="Related Document",
        readonly=True,
        index=True,
    )
    message = fields.Text(
        string="Message Details",
    )
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("queued", "Queued"),
            ("sent", "Accepted by Meta"),
            ("delivered", "Delivered"),
            ("read", "Read"),
            ("failed", "Failed"),
        ],
        string="Status",
        required=True,
        default="queued",
        readonly=True,
        index=True,
    )
    meta_message_id = fields.Char(
        string="Meta Message ID",
        readonly=True,
        index=True,
    )
    error_details = fields.Text(
        string="Error Details",
        readonly=True,
    )
    sent_at = fields.Datetime(
        string="Accepted At",
        readonly=True,
    )
    delivered_at = fields.Datetime(
        string="Delivered At",
        readonly=True,
    )
    read_at = fields.Datetime(
        string="Read At",
        readonly=True,
    )

    def init(self):
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS hotel_whatsapp_log_meta_message_id_idx
            ON hotel_whatsapp_log (meta_message_id)
        """)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                seq = self.env["ir.sequence"].next_by_code("hotel.whatsapp.log")
                vals["name"] = seq or ("WA-" + fields.Datetime.now().strftime("%Y%m%d%H%M%S"))
        return super().create(vals_list)

    def action_set_to_draft(self):
        """Reset a failed or queued WhatsApp notification back to draft state."""
        for log in self:
            if log.status not in ("failed", "queued"):
                raise UserError(_("Only failed or queued WhatsApp messages can be reset to draft."))
            log.write({
                "status": "draft",
                "error_details": False,
            })
        return True

    @api.model
    def _process_webhook_status(self, status_item):
        """
        Process a status item received from Meta WhatsApp Webhook callback.
        Updates matching log record with delivery/read state or exact error details.
        """
        meta_id = status_item.get("id")
        status_val = status_item.get("status")
        timestamp_val = status_item.get("timestamp")
        recipient_id = status_item.get("recipient_id")

        if not meta_id and not recipient_id:
            return False

        log = self.sudo().search([("meta_message_id", "=", meta_id)], limit=1)
        if not log and recipient_id:
            clean_digits = "".join(c for c in str(recipient_id) if c.isdigit())
            log = self.sudo().search([
                ("phone_number", "like", clean_digits),
                ("status", "in", ("queued", "sent")),
            ], order="id desc", limit=1)

        if not log:
            _logger.info("WhatsApp webhook received for unmatched message ID %s, recipient %s", meta_id, recipient_id)
            return False

        dt = (
            datetime.datetime.fromtimestamp(int(timestamp_val))
            if timestamp_val
            else fields.Datetime.now()
        )

        if status_val == "failed":
            errors = status_item.get("errors", [])
            error_lines = []
            for err in errors:
                code = err.get("code")
                title = err.get("title", "")
                msg = err.get("message", "")
                details = err.get("error_data", {}).get("details", "")
                href = err.get("href", "")
                line = f"[Code {code}] {title}: {details or msg}"
                if code == 131047:
                    line += " (More than 24h passed since customer last replied. Free-form text messages require customer message within 24 hours or an approved Meta template.)"
                if href:
                    line += f" - Refer to: {href}"
                error_lines.append(line)

            err_str = "\n".join(error_lines) if error_lines else _("Meta reported message failure with no error details.")

            log.write({
                "status": "failed",
                "error_details": err_str,
            })
            _logger.warning("WhatsApp message %s failed via Webhook: %s", log.name, err_str)

            if log.task_reference and hasattr(log.task_reference, "message_post"):
                try:
                    log.task_reference.message_post(
                        body=Markup("<p class='text-danger'>❌ <b>Meta WhatsApp Delivery Failed</b> (To: %s):<br/>%s</p>")
                        % (escape(log.phone_number or ""), escape(err_str)),
                        subtype_xmlid="mail.mt_note",
                    )
                except Exception as exc:
                    _logger.warning("Failed to post WhatsApp failure note to chatter on %s: %s", log.task_reference, exc)

        elif status_val == "delivered":
            log.write({
                "status": "delivered",
                "delivered_at": dt,
            })
        elif status_val == "read":
            log.write({
                "status": "read",
                "read_at": dt,
            })
        elif status_val == "sent":
            log.write({
                "status": "sent",
                "sent_at": dt,
            })

        return log

    def _send_meta_whatsapp_message(self):
        """Send a single WhatsApp message via Meta Graph API."""
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        company = self.company_id or self.env.company

        whatsapp_enabled = ICP.get_param(
            "vs_hotel_management.whatsapp_enabled", "False"
        ).lower() in ("true", "1", "yes")

        if not whatsapp_enabled:
            err = _("WhatsApp notifications are disabled in settings.")
            self.write({"status": "failed", "error_details": err})
            return False

        token = company.whatsapp_access_token or ICP.get_param(
            "vs_hotel_management.whatsapp_access_token", ""
        )
        phone_number_id = company.whatsapp_phone_number_id or ICP.get_param(
            "vs_hotel_management.whatsapp_phone_number_id", ""
        )
        api_version = (
            company.whatsapp_api_version
            or ICP.get_param("vs_hotel_management.whatsapp_api_version", "v23.0")
            or "v23.0"
        ).strip()

        if not token or not phone_number_id:
            err = _("WhatsApp credentials missing on company '%s'.") % company.name
            self.write({"status": "failed", "error_details": err})
            return False

        phone = "".join(char for char in str(self.phone_number or "") if char.isdigit())
        if not phone or len(phone) < 8:
            err = _("Recipient phone number '%s' is invalid.") % (self.phone_number or "")
            self.write({"status": "failed", "error_details": err})
            return False

        if not self.message:
            err = _("Message text is empty.")
            self.write({"status": "failed", "error_details": err})
            return False

        url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": self.message,
            },
        }

        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=20,
            )
            try:
                result = response.json()
            except ValueError:
                result = {"error": response.text}

            if not response.ok:
                err_msg = (
                    result.get("error", {}).get("message")
                    if isinstance(result.get("error"), dict)
                    else str(result.get("error", result))
                )
                self.write({
                    "status": "failed",
                    "error_details": str(err_msg)[:4000],
                })
                return False

            messages = result.get("messages") or []
            message_id = messages[0].get("id") if messages else False

            if not message_id:
                err_msg = _("Meta response did not contain a message ID: %s") % result
                self.write({
                    "status": "failed",
                    "error_details": str(err_msg)[:4000],
                })
                return False

            self.write({
                "status": "sent",
                "meta_message_id": message_id,
                "sent_at": fields.Datetime.now(),
                "error_details": False,
            })
            _logger.info("WhatsApp notification %s sent successfully to %s (Meta ID: %s)", self.name, phone, message_id)
            return True

        except requests.RequestException as exc:
            err_msg = str(exc)
            self.write({
                "status": "failed",
                "error_details": err_msg[:4000],
            })
            return False

    @api.model
    def cron_process_whatsapp_queue(self, batch_size=50):
        """
        Scheduled Action / Cron Job:
        Process queued WhatsApp notifications asynchronously in batches.
        """
        queued_logs = self.search([("status", "=", "queued")], limit=batch_size, order="create_date asc, id asc")
        if not queued_logs:
            _logger.debug("No queued WhatsApp notifications to process.")
            return True

        _logger.info("Processing %d queued WhatsApp notification(s)...", len(queued_logs))
        for log in queued_logs:
            try:
                log._send_meta_whatsapp_message()
                if not config['test_enable']:
                    self.env.cr.commit()
            except Exception as e:
                if not config['test_enable']:
                    self.env.cr.rollback()
                _logger.exception("Error processing WhatsApp log %s: %s", log.name, e)
                try:
                    log.write({"status": "failed", "error_details": str(e)[:4000]})
                    if not config['test_enable']:
                        self.env.cr.commit()
                except Exception:
                    if not config['test_enable']:
                        self.env.cr.rollback()

        return True

    @api.model
    def cron_process_email_sms_queue(self, batch_size=50):
        """
        Scheduled Action / Cron Job:
        Process queued outgoing Emails and SMS messages in batches so
        notifications are sent shortly after actions without delaying the UI.
        """
        # 1. Process Mail Queue (outgoing mail.mail records)
        try:
            if "mail.mail" in self.env:
                self.env["mail.mail"].sudo().process_email_queue()
                _logger.debug("Odoo mail queue processed by hotel notification cron.")
        except Exception as e:
            _logger.warning("Failed to trigger process_email_queue: %s", e)

        # 2. Process SMS Queue (outgoing sms.sms records)
        try:
            if "sms.sms" in self.env and hasattr(self.env["sms.sms"], "_process_queue"):
                self.env["sms.sms"].sudo()._process_queue()
                _logger.debug("Odoo SMS queue processed by hotel notification cron.")
        except Exception as e:
            _logger.warning("Failed to trigger sms._process_queue: %s", e)

        return True

    @api.model
    def cron_process_all_notification_queues(self):
        """Process WhatsApp, Email, and SMS notification queues in a single cron run."""
        self.cron_process_whatsapp_queue()
        self.cron_process_email_sms_queue()
        return True

    def action_resend(self):
        """Resend or dispatch the WhatsApp message using company credentials and Meta Graph API."""
        sent_logs = self.env["hotel.whatsapp.log"]
        failed_errors = []

        for log in self:
            if log.status not in ("draft", "failed", "queued"):
                continue

            success = log._send_meta_whatsapp_message()
            if success:
                sent_logs |= log
            else:
                failed_errors.append(f"{log.name}: {log.error_details or _('Failed to send')}")

        if failed_errors and not sent_logs:
            raise UserError(_("Failed to send WhatsApp notification(s):\n\n%s") % "\n".join(failed_errors))

        if failed_errors:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("WhatsApp Processed with Warnings"),
                    "message": _("%(sent)s sent successfully. Errors occurred on:\n%(errors)s") % {
                        "sent": len(sent_logs),
                        "errors": "\n".join(failed_errors),
                    },
                    "type": "warning",
                    "sticky": True,
                },
            }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("WhatsApp Sent Successfully"),
                "message": _("%s WhatsApp message(s) sent successfully.") % len(sent_logs),
                "type": "success",
                "sticky": False,
            },
        }
