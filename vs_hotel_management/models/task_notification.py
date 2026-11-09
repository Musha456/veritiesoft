from markupsafe import Markup, escape
from odoo import models, fields, api, _
import requests
import logging
import pytz

_logger = logging.getLogger(__name__)


class HotelNotificationMixin(models.AbstractModel):
    """
    Base Reusable Notification Mixin for Hotel Management System.
    Provides unified notification dispatching across Email, WhatsApp, and SMS channels.
    Designed for reservations, housekeeping, maintenance, and future addon modules
    (laundry, banquet, transport, restaurant, pos, etc.).
    """
    _name = "hotel.notification.mixin"
    _description = "Hotel Notification Mixin"

    def _get_local_timezone(self, partner=None):
        """Determine effective timezone: recipient partner -> hotel -> user -> company -> UTC."""
        partner = partner or getattr(self, "partner_id", False)
        hotel = getattr(self, "hotel_id", False)
        if not hotel and hasattr(self, "room_id") and self.room_id:
            hotel = getattr(self.room_id, "hotel_id", False)
        tz_name = (
            (partner and partner.tz)
            or (hotel and hotel.timezone)
            or self.env.user.tz
            or self.env.company.partner_id.tz
            or "UTC"
        )
        try:
            return pytz.timezone(tz_name)
        except Exception:
            return pytz.UTC

    def _format_datetime_local(self, dt, partner=None, dt_format="%d %b %Y, %I:%M %p"):
        """Convert UTC datetime into the recipient/hotel local timezone formatted string."""
        if not dt:
            return ""
        tz = self._get_local_timezone(partner=partner)
        if not dt.tzinfo:
            dt = pytz.UTC.localize(dt)
        return dt.astimezone(tz).strftime(dt_format)

    # ---------------------------------------------------------
    # Helper: WhatsApp Credentials
    # ---------------------------------------------------------

    def _get_company_whatsapp_credentials(self):
        """Retrieve Meta WhatsApp credentials for the record's company with fallback to ICP."""
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        company = getattr(self, "company_id", False) or self.env.company

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
        template_name = company.whatsapp_template_name or ICP.get_param(
            "vs_hotel_management.whatsapp_template_name", "hotel_task_notification"
        )
        template_lang = company.whatsapp_template_language or ICP.get_param(
            "vs_hotel_management.whatsapp_template_language", "en"
        )

        return token, phone_number_id, api_version, template_name, template_lang

    # ---------------------------------------------------------
    # Channel Activation Helpers
    # ---------------------------------------------------------

    @api.model
    def _is_whatsapp_channel_enabled(self):
        """Check if WhatsApp is enabled globally or in any operational module."""
        ICP = self.env["ir.config_parameter"].sudo()
        if ICP.get_param("vs_hotel_management.whatsapp_enabled", "False").lower() in ("true", "1", "yes"):
            return True
        for key in (
            "vs_hotel_management.notify_reservation_whatsapp",
            "vs_hotel_management.notify_housekeeping_whatsapp",
            "vs_hotel_management.notify_maintenance_whatsapp",
        ):
            if ICP.get_param(key, "False").lower() in ("true", "1", "yes"):
                return True
        return False

    @api.model
    def _is_email_channel_enabled(self):
        """Check if Email is enabled globally or in any operational module."""
        ICP = self.env["ir.config_parameter"].sudo()
        if ICP.get_param("vs_hotel_management.email_enabled", "True").lower() in ("true", "1", "yes"):
            return True
        for key in (
            "vs_hotel_management.notify_reservation_email",
            "vs_hotel_management.notify_housekeeping_email",
            "vs_hotel_management.notify_maintenance_email",
        ):
            if ICP.get_param(key, "False").lower() in ("true", "1", "yes"):
                return True
        return False

    @api.model
    def _is_sms_channel_enabled(self):
        """Check if SMS is enabled globally or in any operational module."""
        ICP = self.env["ir.config_parameter"].sudo()
        if ICP.get_param("vs_hotel_management.sms_enabled", "False").lower() in ("true", "1", "yes"):
            return True
        for key in (
            "vs_hotel_management.notify_reservation_sms",
            "vs_hotel_management.notify_housekeeping_sms",
            "vs_hotel_management.notify_maintenance_sms",
        ):
            if ICP.get_param(key, "False").lower() in ("true", "1", "yes"):
                return True
        return False

    # ---------------------------------------------------------
    # WhatsApp Dispatcher
    # ---------------------------------------------------------

    def _send_whatsapp_message(self, recipient, message_text, log_values=None, force_send=False):
        """
        Queue or send a WhatsApp text message using the record's company credentials.
        Default force_send=False queues the message for background dispatch via cron,
        guaranteeing snappy and smooth UI button interactions.
        """
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        Log = self.env["hotel.whatsapp.log"].sudo()
        company = getattr(self, "company_id", False) or self.env.company

        whatsapp_enabled = self._is_whatsapp_channel_enabled()

        phone = "".join(char for char in str(recipient or "") if char.isdigit())

        vals = {
            "company_id": company.id,
            "status": "queued",
            "phone_number": phone or str(recipient or ""),
            "task_reference": f"{self._name},{self.id}",
            "message": (message_text or "")[:4000],
        }
        if log_values:
            vals.update(log_values)

        if not whatsapp_enabled:
            vals["status"] = "failed"
            vals["error_details"] = _("WhatsApp notifications are disabled in settings.")
            log = Log.create(vals)
            _logger.info("WhatsApp skipped (disabled) for %s (%s)", self.display_name, recipient)
            return log

        if not phone or len(phone) < 8:
            vals["status"] = "failed"
            vals["error_details"] = _("Recipient phone number is invalid: '%s'.") % (recipient or "")
            log = Log.create(vals)
            _logger.warning("WhatsApp failed for %s: invalid phone '%s'", self.display_name, recipient)
            return log

        log = Log.create(vals)
        _logger.info("WhatsApp notification queued for %s (Log %s)", recipient, log.name)

        if force_send:
            log._send_meta_whatsapp_message()

        return log

    def _send_whatsapp_template(self, recipient, parameters, log_values=None, template_name=None, language=None, force_send=False):
        """
        Queue or send a WhatsApp notification using Meta parameters or template fallback.
        Default force_send=False queues the message for background dispatch via cron,
        avoiding network lag during action button clicks.
        """
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        Log = self.env["hotel.whatsapp.log"].sudo()
        company = getattr(self, "company_id", False) or self.env.company

        whatsapp_enabled = self._is_whatsapp_channel_enabled()

        phone = "".join(char for char in str(recipient or "") if char.isdigit())

        # Build formatted text fallback message
        if len(parameters) >= 10:
            formatted_message = (
                f"*{parameters[0]} — Task Notification*\n\n"
                f"*Building:* {parameters[1]}\n"
                f"*Floor:* {parameters[2]}\n"
                f"*Room:* {parameters[3]}\n"
                f"*Task:* {parameters[4]} — {parameters[5]}\n"
                f"*Scheduled:* {parameters[6]}\n"
                f"*Status:* {parameters[7]}\n"
                f"*Instructions:* {parameters[8]}\n\n"
                f"*View Task:* {parameters[9]}"
            )
        else:
            formatted_message = "\n".join(str(p or "-") for p in parameters)

        vals = {
            "company_id": company.id,
            "status": "queued",
            "phone_number": phone or str(recipient or ""),
            "task_reference": f"{self._name},{self.id}",
            "message": (formatted_message or "")[:4000],
        }
        if log_values:
            vals.update(log_values)

        if not whatsapp_enabled:
            vals["status"] = "failed"
            vals["error_details"] = _("WhatsApp notifications are disabled in settings.")
            log = Log.create(vals)
            _logger.info("WhatsApp template skipped (disabled) for %s (%s)", self.display_name, recipient)
            return log

        if not phone or len(phone) < 8:
            vals["status"] = "failed"
            vals["error_details"] = _("Recipient phone number is invalid: '%s'.") % (recipient or "")
            log = Log.create(vals)
            _logger.warning("WhatsApp template failed for %s: invalid phone '%s'", self.display_name, recipient)
            return log

        log = Log.create(vals)
        _logger.info("WhatsApp template notification queued for %s (Log %s)", recipient, log.name)

        if force_send:
            log._send_meta_whatsapp_message()

        return log

    # ---------------------------------------------------------
    # Email Dispatcher
    # ---------------------------------------------------------

    def _send_notification_email(self, template_xmlid=None, subject=None, body_html=None, partner_id=None, force_send=False):
        """
        Queue an email notification via mail.template or message_post.
        Default force_send=False queues emails into mail.mail (outgoing state)
        so SMTP delivery is processed asynchronously via scheduled cron job.
        """
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        email_enabled = self._is_email_channel_enabled()

        if not email_enabled:
            return False

        partner = partner_id or getattr(self, "partner_id", False)
        if partner and hasattr(partner, "email") and not partner.email:
            _logger.warning("Recipient '%s' on %s has no email address configured.", partner.name, self.display_name)
            if hasattr(self, "message_post"):
                self.message_post(
                    body=Markup("<p class='text-warning'>⚠️ <b>Email Notification Skipped:</b> Guest / recipient <b>%s</b> has no email address configured.</p>")
                    % escape(partner.name or "Guest"),
                    subtype_xmlid="mail.mt_note",
                )
            return False

        if template_xmlid:
            template = self.env.ref(template_xmlid, raise_if_not_found=False)
            if template:
                try:
                    if hasattr(self, "message_post_with_source"):
                        self.with_context(
                            mail_post_autofollow=True,
                            mail_notify_force_send=False,
                        ).message_post_with_source(
                            template,
                            subtype_xmlid="mail.mt_comment",
                        )
                    else:
                        template.with_context(mail_notify_force_send=False).send_mail(
                            self.id, force_send=force_send, raise_exception=False
                        )
                    return True
                except Exception as e:
                    _logger.warning("Failed to dispatch email template %s via message_post_with_source on %s: %s. Retrying via send_mail.", template_xmlid, self.display_name, e)
                    try:
                        template.with_context(mail_notify_force_send=False).send_mail(
                            self.id, force_send=force_send, raise_exception=False
                        )
                        return True
                    except Exception as err:
                        _logger.error("send_mail also failed for %s: %s", self.display_name, err)

        if body_html and partner:
            try:
                pid = partner.id if hasattr(partner, "id") else partner
                self.with_context(mail_notify_force_send=False).message_post(
                    body=body_html,
                    subject=subject or _("Hotel Notification"),
                    partner_ids=[pid],
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                    email_layout_xmlid="mail.mail_notification_light",
                )
                return True
            except Exception as e:
                _logger.warning("Failed to post email message on %s: %s", self.display_name, e)

        return False

    # ---------------------------------------------------------
    # SMS Dispatcher
    # ---------------------------------------------------------

    def _send_notification_sms(self, recipient, message_text, force_send=False):
        """
        Send an SMS notification or place in SMS queue with fallback to chatter log.
        Default force_send=False keeps SMS in outgoing queue to avoid blocking user actions.
        """
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        sms_enabled = self._is_sms_channel_enabled()

        if not sms_enabled or not recipient:
            return False

        phone = "".join(char for char in str(recipient) if char.isdigit() or char == "+")
        if not phone or len(phone) < 8:
            return False

        company = getattr(self, "company_id", False) or self.env.company
        if "hotel.sms.service" in self.env:
            try:
                return self.env["hotel.sms.service"].send_sms(
                    to_number=phone,
                    body=message_text,
                    company=company,
                )
            except Exception as e:
                _logger.warning("hotel.sms.service failed for %s: %s", self.display_name, e)

        # If Odoo SMS module is installed, use sms.sms
        if "sms.sms" in self.env:
            try:
                sms = self.env["sms.sms"].sudo().create({
                    "number": phone,
                    "body": message_text,
                })
                if force_send:
                    sms.send()
                    _logger.info("SMS force-sent to %s for %s", phone, self.display_name)
                else:
                    _logger.info("SMS queued for %s for %s (SMS ID: %s)", phone, self.display_name, sms.id)
                return True
            except Exception as e:
                _logger.warning("sms.sms failed for %s: %s", self.display_name, e)

        # Log to chatter
        self.message_post(
            body=Markup("<p><b>📱 SMS Queued:</b><br/><b>To:</b> %s<br/>%s</p>")
            % (escape(phone), escape(message_text)),
            subtype_xmlid="mail.mt_note",
        )
        return True


class HotelTaskNotificationMixin(models.AbstractModel):
    """
    Task-specific notification mixin inheriting from HotelNotificationMixin.
    Handles assignment and cancellation notifications for Housekeeping, Maintenance,
    and any future task types.
    """
    _name = "hotel.task.notification.mixin"
    _description = "Hotel Task Notification Mixin"
    _inherit = "hotel.notification.mixin"

    def _notify_assigned_user(self, event="assigned"):
        """Send HTML email notification to assigned user when task is assigned or cancelled."""
        ICP = self.env["ir.config_parameter"].sudo()
        base_url = ICP.get_param("web.base.url", "").rstrip("/")

        for task in self:
            task_type = (
                "housekeeping"
                if task._name == "hotel.housekeeping"
                else "maintenance"
            )
            config_key = f"vs_hotel_management.notify_{task_type}_email"
            if ICP.get_param(config_key, "True").lower() not in ("true", "1", "yes"):
                continue

            user = task.assigned_to
            if not user:
                continue

            room = task.room_id
            hotel = getattr(task, "hotel_id", False)
            if not hotel and room:
                hotel = getattr(room, "hotel_id", False)

            is_housekeeping = task._name == "hotel.housekeeping"
            detail_field = (
                "housekeeping_type" if is_housekeeping
                else "maintenance_type"
            )
            task_label = (
                _("Housekeeping Task") if is_housekeeping
                else _("Maintenance Task")
            )
            type_label = (
                _("Housekeeping Type") if is_housekeeping
                else _("Maintenance Type")
            )

            detail_value = getattr(task, detail_field, False)
            detail = dict(
                task._fields[detail_field].selection
            ).get(detail_value, detail_value or _("Not specified"))

            building = getattr(room, "building_id", False) if room else False
            floor = getattr(room, "floor_id", False) if room else False

            scheduled_datetime = _("Not scheduled")
            if task.scheduled_date:
                scheduled_datetime = task._format_datetime_local(task.scheduled_date)

            state = dict(
                task._fields["state"].selection
            ).get(task.state, task.state)

            instructions = (
                getattr(task, "instruction_notes", False)
                or _("No additional instructions")
            )

            cancelled = event == "cancelled"
            subject = (
                _("%s Cancelled") % task_label
                if cancelled
                else _("%s Assigned") % task_label
            )
            intro = (
                _("This task has been cancelled.")
                if cancelled
                else _("A task has been assigned to you.")
            )

            logo_html = Markup("")
            if hotel and "logo" in hotel._fields and hotel.logo:
                logo_url = f"{base_url}/web/image/{hotel._name}/{hotel.id}/logo"
                logo_html = Markup(
                    '<img src="{}" alt="Hotel Logo" '
                    'style="max-width:100px;max-height:65px;'
                    'object-fit:contain;margin-bottom:8px;"/>'
                ).format(escape(logo_url))

            task_url = f"{base_url}/web#id={task.id}&model={task._name}&view_type=form"

            body = Markup(
                '<div style="font-family:Arial,sans-serif;'
                'max-width:600px;color:#334155;">'
                '<div style="padding:20px;background:#f8fafc;'
                'border-bottom:3px solid #059669;">'
                '{logo}'
                '<h2 style="margin:0;color:#0f172a;">{hotel}</h2>'
                '</div>'
                '<div style="padding:20px;">'
                '<p>{intro}</p>'
                '<table style="width:100%;border-collapse:collapse;">'
                '<tr><td style="padding:9px;border-bottom:1px solid #e2e8f0;">'
                '<strong>Building</strong></td><td style="padding:9px;'
                'border-bottom:1px solid #e2e8f0;">{building}</td></tr>'
                '<tr><td style="padding:9px;border-bottom:1px solid #e2e8f0;">'
                '<strong>Floor</strong></td><td style="padding:9px;'
                'border-bottom:1px solid #e2e8f0;">{floor}</td></tr>'
                '<tr><td style="padding:9px;border-bottom:1px solid #e2e8f0;">'
                '<strong>Room</strong></td><td style="padding:9px;'
                'border-bottom:1px solid #e2e8f0;">{room}</td></tr>'
                '<tr><td style="padding:9px;border-bottom:1px solid #e2e8f0;">'
                '<strong>{type_label}</strong></td><td style="padding:9px;'
                'border-bottom:1px solid #e2e8f0;">{detail}</td></tr>'
                '<tr><td style="padding:9px;border-bottom:1px solid #e2e8f0;">'
                '<strong>Scheduled Time</strong></td><td style="padding:9px;'
                'border-bottom:1px solid #e2e8f0;">{scheduled}</td></tr>'
                '<tr><td style="padding:9px;border-bottom:1px solid #e2e8f0;">'
                '<strong>Status</strong></td><td style="padding:9px;'
                'border-bottom:1px solid #e2e8f0;">{state}</td></tr>'
                '<tr><td style="padding:9px;vertical-align:top;">'
                '<strong>Instructions</strong></td><td style="padding:9px;">'
                '{instructions}</td></tr>'
                '</table>'
                '<div style="margin-top:26px;text-align:center;">'
                '<a href="{url}" '
                'style="display:inline-block;'
                'background:#059669;'
                'color:#ffffff;'
                'font-family:Arial,sans-serif;'
                'font-size:14px;'
                'font-weight:600;'
                'line-height:20px;'
                'padding:12px 28px;'
                'text-decoration:none;'
                'border-radius:6px;'
                'border:1px solid #047857;">'
                'View Task Details &#8594;'
                '</a>'
                '<p style="margin:10px 0 0;color:#64748b;font-size:12px;">'
                'Open the task to review its details and instructions.'
                '</p>'
                '</div>'
                '</div></div>'
            ).format(
                logo=logo_html,
                hotel=escape(hotel.name if hotel else _("Hotel")),
                intro=escape(intro),
                building=escape(building.name if building else _("Not specified")),
                floor=escape(floor.name if floor else _("Not specified")),
                room=escape(room.display_name if room else _("Not specified")),
                type_label=escape(type_label),
                detail=escape(detail),
                scheduled=escape(scheduled_datetime),
                state=escape(state),
                instructions=escape(instructions),
                url=escape(task_url),
            )

            task.with_context(
                mail_post_autofollow=True,
                mail_notify_force_send=False,
            ).message_post(
                author_id=self.env.user.partner_id.id,
                body=body,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                email_layout_xmlid="mail.mail_notification_light",
                partner_ids=[user.id],
                subject=subject,
            )

    def _notify_whatsapp_task(self, event="assigned"):
        """Send WhatsApp notification to assigned staff member if enabled."""
        ICP = self.env["ir.config_parameter"].sudo()

        for task in self:
            task_type = (
                "housekeeping"
                if task._name == "hotel.housekeeping"
                else "maintenance"
            )

            config_key = f"vs_hotel_management.notify_{task_type}_whatsapp"
            if ICP.get_param(config_key, "False").lower() not in ("true", "1", "yes"):
                continue

            partner = task.assigned_to
            phone = getattr(partner, "mobile", False) or partner.phone

            if not phone:
                _logger.warning(
                    "WhatsApp skipped for task %s: assigned user has no phone number.",
                    task.display_name,
                )
                continue

            recipient = "".join(char for char in phone if char.isdigit())
            room = task.room_id
            hotel = getattr(task, "hotel_id", False)
            if not hotel and room:
                hotel = getattr(room, "hotel_id", False)

            detail_field = (
                "housekeeping_type" if task_type == "housekeeping"
                else "maintenance_type"
            )
            detail_value = getattr(task, detail_field, False)
            detail = dict(
                task._fields[detail_field].selection
            ).get(detail_value, detail_value or _("Not specified"))

            building = getattr(room, "building_id", False) if room else False
            floor = getattr(room, "floor_id", False) if room else False

            scheduled = (
                task.scheduled_date.strftime("%d %b %Y, %I:%M %p")
                if task.scheduled_date
                else _("Not scheduled")
            )
            status = dict(task._fields["state"].selection).get(task.state, task.state)

            base_url = ICP.get_param("web.base.url", "").rstrip("/")
            task_url = f"{base_url}/web#id={task.id}&model={task._name}&view_type=form"

            parameters = [
                hotel.name if hotel else _("Hotel"),
                building.name if building else _("Not specified"),
                floor.name if floor else _("Not specified"),
                room.display_name if room else _("Not specified"),
                _("Housekeeping Type") if task_type == "housekeeping" else _("Maintenance Type"),
                detail,
                scheduled,
                status,
                getattr(task, "instruction_notes", False) or _("No additional instructions"),
                task_url,
            ]

            task._send_whatsapp_template(
                recipient=recipient,
                parameters=parameters,
                log_values={
                    "recipient_id": partner.id,
                    "phone_number": recipient,
                    "task_type": task_type,
                    "event": event,
                    "task_reference": f"{task._name},{task.id}",
                    "message": f"{task_type.title()} task {event}. Room: {room.display_name if room else '-'}",
                },
            )

    def _notify_sms_task(self, event="assigned"):
        """Send SMS notification to assigned staff member if enabled."""
        ICP = self.env["ir.config_parameter"].sudo()

        for task in self:
            task_type = (
                "housekeeping"
                if task._name == "hotel.housekeeping"
                else "maintenance"
            )
            config_key = f"vs_hotel_management.notify_{task_type}_sms"
            if ICP.get_param(config_key, "False").lower() not in ("true", "1", "yes"):
                continue

            partner = task.assigned_to if task.assigned_to else False
            if not partner:
                continue

            phone = getattr(partner, "mobile", False) or partner.phone
            if not phone:
                continue

            room_name = task.room_id.display_name if task.room_id else _("Room")
            task_type_label = _("Checkout Cleaning") if getattr(task, "housekeeping_type", "") == "checkout" else _("Task")
            if event == "cancelled":
                msg = _("Hotel Task Cancelled: %s for %s has been cancelled.") % (
                    task_type_label,
                    room_name,
                )
            else:
                msg = _("Hotel Task: New %s assigned for %s. Instructions: %s") % (
                    task_type_label,
                    room_name,
                    getattr(task, "instruction_notes", False) or _("Please clean the room."),
                )
            task._send_notification_sms(recipient=phone, message_text=msg)

    def _notify_assigned_partner(self, event="assigned"):
        """Alias for _notify_assigned_user — used when assigned_to is already a partner."""
        return self._notify_assigned_user(event=event)

    def _notify_inspection_required(self, inspector_partner):
        """Notify inspector that a task requires their inspection."""
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        base_url = ICP.get_param("web.base.url", "").rstrip("/")

        task_type = (
            "housekeeping" if self._name == "hotel.housekeeping" else "maintenance"
        )
        task_label = (
            _("Housekeeping Task") if task_type == "housekeeping"
            else _("Maintenance Task")
        )

        if not inspector_partner:
            return

        room = self.room_id
        hotel = getattr(self, "hotel_id", False)
        if not hotel and room:
            hotel = getattr(room, "hotel_id", False)

        task_url = f"{base_url}/web#id={self.id}&model={self._name}&view_type=form"
        subject = _("%s — Inspection Required") % task_label

        body = Markup(
            '<div style="font-family:Arial,sans-serif;max-width:600px;color:#334155;">'
            '<div style="padding:20px;background:#fef9c3;border-bottom:3px solid #ca8a04;">'
            '<h2 style="margin:0;color:#0f172a;">🔍 {title}</h2>'
            '</div>'
            '<div style="padding:20px;">'
            '<p>{intro}</p>'
            '<table style="width:100%;border-collapse:collapse;">'
            '<tr><td style="padding:9px;border-bottom:1px solid #e2e8f0;"><strong>Room</strong></td>'
            '<td style="padding:9px;border-bottom:1px solid #e2e8f0;">{room}</td></tr>'
            '<tr><td style="padding:9px;border-bottom:1px solid #e2e8f0;"><strong>Hotel</strong></td>'
            '<td style="padding:9px;border-bottom:1px solid #e2e8f0;">{hotel}</td></tr>'
            '<tr><td style="padding:9px;"><strong>Assigned Staff</strong></td>'
            '<td style="padding:9px;">{staff}</td></tr>'
            '</table>'
            '<div style="margin-top:26px;text-align:center;">'
            '<a href="{url}" style="display:inline-block;background:#ca8a04;color:#ffffff;'
            'font-family:Arial,sans-serif;font-size:14px;font-weight:600;line-height:20px;'
            'padding:12px 28px;text-decoration:none;border-radius:6px;">'
            'View &amp; Inspect Task &#8594;'
            '</a></div></div></div>'
        ).format(
            title=escape(subject),
            intro=escape(_("A task is ready for your inspection.")),
            room=escape(room.display_name if room else _("Not specified")),
            hotel=escape(hotel.name if hotel else _("Hotel")),
            staff=escape(self.assigned_to.name if self.assigned_to else _("Not assigned")),
            url=escape(task_url),
        )

        config_key = f"vs_hotel_management.notify_{task_type}_email"
        if ICP.get_param(config_key, "True").lower() in ("true", "1", "yes"):
            self.with_context(
                mail_post_autofollow=True,
                mail_notify_force_send=False,
            ).message_post(
                author_id=self.env.user.partner_id.id,
                body=body,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                email_layout_xmlid="mail.mail_notification_light",
                partner_ids=[inspector_partner.id],
                subject=subject,
            )

        # WhatsApp to inspector
        config_wa = f"vs_hotel_management.notify_{task_type}_whatsapp"
        if ICP.get_param(config_wa, "False").lower() in ("true", "1", "yes"):
            phone = getattr(inspector_partner, "mobile", False) or inspector_partner.phone
            if phone:
                recipient = "".join(c for c in phone if c.isdigit())
                msg = _(
                    "Inspection Required: %s for Room %s is ready for your inspection. "
                    "Assigned staff: %s"
                ) % (
                    task_label,
                    room.display_name if room else "-",
                    self.assigned_to.name if self.assigned_to else "-",
                )
                self._send_whatsapp_message(
                    recipient=recipient,
                    message_text=msg,
                    log_values={
                        "recipient_id": inspector_partner.id,
                        "task_type": task_type,
                        "event": "inspection_required",
                        "task_reference": f"{self._name},{self.id}",
                    },
                )

    def _notify_inspection_passed(self):
        """Notify assigned staff that inspection passed."""
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        base_url = ICP.get_param("web.base.url", "").rstrip("/")

        task_type = (
            "housekeeping" if self._name == "hotel.housekeeping" else "maintenance"
        )
        task_label = (
            _("Housekeeping Task") if task_type == "housekeeping"
            else _("Maintenance Task")
        )

        if not self.assigned_to:
            return

        room = self.room_id
        task_url = f"{base_url}/web#id={self.id}&model={self._name}&view_type=form"
        subject = _("%s — Inspection Passed ✅") % task_label

        body = Markup(
            '<div style="font-family:Arial,sans-serif;max-width:600px;color:#334155;">'
            '<div style="padding:20px;background:#dcfce7;border-bottom:3px solid #16a34a;">'
            '<h2 style="margin:0;color:#0f172a;">✅ {title}</h2>'
            '</div>'
            '<div style="padding:20px;">'
            '<p>{intro}</p>'
            '<p><strong>Room:</strong> {room}</p>'
            '<div style="margin-top:20px;text-align:center;">'
            '<a href="{url}" style="display:inline-block;background:#16a34a;color:#ffffff;'
            'font-family:Arial,sans-serif;font-size:14px;font-weight:600;'
            'padding:12px 28px;text-decoration:none;border-radius:6px;">'
            'View Task &#8594;</a></div></div></div>'
        ).format(
            title=escape(subject),
            intro=escape(_("Great work! Your task has passed inspection and is marked as complete.")),
            room=escape(room.display_name if room else _("Not specified")),
            url=escape(task_url),
        )

        config_key = f"vs_hotel_management.notify_{task_type}_email"
        if ICP.get_param(config_key, "True").lower() in ("true", "1", "yes"):
            self.with_context(
                mail_post_autofollow=True,
                mail_notify_force_send=False,
            ).message_post(
                author_id=self.env.user.partner_id.id,
                body=body,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                email_layout_xmlid="mail.mail_notification_light",
                partner_ids=[self.assigned_to.id],
                subject=subject,
            )

        # WhatsApp to assigned staff
        config_wa = f"vs_hotel_management.notify_{task_type}_whatsapp"
        if ICP.get_param(config_wa, "False").lower() in ("true", "1", "yes"):
            phone = getattr(self.assigned_to, "mobile", False) or self.assigned_to.phone
            if phone:
                recipient = "".join(c for c in phone if c.isdigit())
                msg = _("Inspection Passed ✅: Your %s for Room %s has passed inspection and is now complete.") % (
                    task_label, room.display_name if room else "-"
                )
                self._send_whatsapp_message(
                    recipient=recipient,
                    message_text=msg,
                    log_values={
                        "recipient_id": self.assigned_to.id,
                        "task_type": task_type,
                        "event": "inspection_passed",
                        "task_reference": f"{self._name},{self.id}",
                    },
                )

    def _notify_inspection_failed(self, remarks):
        """Notify assigned staff that inspection failed with revision required."""
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        base_url = ICP.get_param("web.base.url", "").rstrip("/")

        task_type = (
            "housekeeping" if self._name == "hotel.housekeeping" else "maintenance"
        )
        task_label = (
            _("Housekeeping Task") if task_type == "housekeeping"
            else _("Maintenance Task")
        )

        if not self.assigned_to:
            return

        room = self.room_id
        task_url = f"{base_url}/web#id={self.id}&model={self._name}&view_type=form"
        subject = _("%s — Revision Required ⚠️") % task_label

        body = Markup(
            '<div style="font-family:Arial,sans-serif;max-width:600px;color:#334155;">'
            '<div style="padding:20px;background:#fee2e2;border-bottom:3px solid #dc2626;">'
            '<h2 style="margin:0;color:#0f172a;">⚠️ {title}</h2>'
            '</div>'
            '<div style="padding:20px;">'
            '<p>{intro}</p>'
            '<p><strong>Room:</strong> {room}</p>'
            '<p><strong>Inspector Remarks:</strong></p>'
            '<blockquote style="border-left:4px solid #dc2626;margin:0;padding:8px 16px;'
            'background:#fff1f2;color:#991b1b;">{remarks}</blockquote>'
            '<div style="margin-top:20px;text-align:center;">'
            '<a href="{url}" style="display:inline-block;background:#dc2626;color:#ffffff;'
            'font-family:Arial,sans-serif;font-size:14px;font-weight:600;'
            'padding:12px 28px;text-decoration:none;border-radius:6px;">'
            'View Task &amp; Revise &#8594;</a></div></div></div>'
        ).format(
            title=escape(subject),
            intro=escape(_("Your task did not pass inspection. Please address the issues and resubmit.")),
            room=escape(room.display_name if room else _("Not specified")),
            remarks=escape(remarks or _("No remarks provided.")),
            url=escape(task_url),
        )

        config_key = f"vs_hotel_management.notify_{task_type}_email"
        if ICP.get_param(config_key, "True").lower() in ("true", "1", "yes"):
            self.with_context(
                mail_post_autofollow=True,
                mail_notify_force_send=False,
            ).message_post(
                author_id=self.env.user.partner_id.id,
                body=body,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                email_layout_xmlid="mail.mail_notification_light",
                partner_ids=[self.assigned_to.id],
                subject=subject,
            )

        # WhatsApp to assigned staff
        config_wa = f"vs_hotel_management.notify_{task_type}_whatsapp"
        if ICP.get_param(config_wa, "False").lower() in ("true", "1", "yes"):
            phone = getattr(self.assigned_to, "mobile", False) or self.assigned_to.phone
            if phone:
                recipient = "".join(c for c in phone if c.isdigit())
                msg = _(
                    "Revision Required ⚠️: Your %s for Room %s requires revision. "
                    "Remarks: %s"
                ) % (task_label, room.display_name if room else "-", remarks or "-")
                self._send_whatsapp_message(
                    recipient=recipient,
                    message_text=msg,
                    log_values={
                        "recipient_id": self.assigned_to.id,
                        "task_type": task_type,
                        "event": "inspection_failed",
                        "task_reference": f"{self._name},{self.id}",
                    },
                )
