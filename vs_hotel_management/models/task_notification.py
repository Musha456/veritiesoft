from markupsafe import Markup, escape

from odoo import models, fields, _

import requests
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class HotelTaskNotificationMixin(models.AbstractModel):
    _name = "hotel.task.notification.mixin"
    _description = "Hotel Task Notification Mixin"

    def _notify_assigned_user(self, event="assigned"):
        ICP = self.env["ir.config_parameter"].sudo()
        base_url = ICP.get_param("web.base.url", "").rstrip("/")

        for task in self:
            user = task.assigned_to
            if not user or not user.partner_id:
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
                scheduled_datetime = (
                    task.scheduled_date.strftime("%d %b %Y, %I:%M %p")
                    .lstrip("0")
                )

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
                logo_url = (
                    f"{base_url}/web/image/"
                    f"{hotel._name}/{hotel.id}/logo"
                )
                logo_html = Markup(
                    '<img src="{}" alt="Hotel Logo" '
                    'style="max-width:100px;max-height:65px;'
                    'object-fit:contain;margin-bottom:8px;"/>'
                ).format(escape(logo_url))

            task_url = (
                f"{base_url}/web#id={task.id}"
                f"&model={task._name}&view_type=form"
            )

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
                '<p style="margin-top:22px;">'
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
                '</p></div></div>'
            ).format(
                logo=logo_html,
                hotel=escape(hotel.name if hotel else _("Hotel")),
                intro=escape(intro),
                building=escape(
                    building.name if building else _("Not specified")
                ),
                floor=escape(
                    floor.name if floor else _("Not specified")
                ),
                room=escape(
                    room.display_name if room else _("Not specified")
                ),
                type_label=escape(type_label),
                detail=escape(detail),
                scheduled=escape(scheduled_datetime),
                state=escape(state),
                instructions=escape(instructions),
                url=escape(task_url),
            )

            task.message_post(
                author_id=self.env.user.partner_id.id,
                body=body,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                email_layout_xmlid="mail.mail_notification_light",
                partner_ids=[user.partner_id.id],
                subject=subject,
            )

    def _send_whatsapp_template(self, recipient, parameters, log_values):
        ICP = self.env["ir.config_parameter"].sudo()
        Log = self.env["hotel.whatsapp.log"].sudo()

        log = Log.create({
            **log_values,
            "status": "queued",
        })

        def mark_failed(error):
            log.write({
                "status": "failed",
                "error_details": str(error)[:4000],
            })
            return False

        enabled = ICP.get_param(
            "vs_hotel_management.whatsapp_enabled", "False"
        ).lower() in ("true", "1", "yes")

        if not enabled:
            return mark_failed(_("WhatsApp notifications are disabled."))

        token = ICP.get_param(
            "vs_hotel_management.whatsapp_access_token"
        )
        phone_number_id = ICP.get_param(
            "vs_hotel_management.whatsapp_phone_number_id"
        )
        api_version = ICP.get_param(
            "vs_hotel_management.whatsapp_api_version", "v23.0"
        )

        template = self.env["hotel.whatsapp.template"].sudo().search([
            ("template_key", "=", "hotel_task_notification"),
            ("language", "=", "en"),
            ("active", "=", True),
            ("meta_status", "=", "approved"),
        ], limit=1)

        if not template:
            return mark_failed(
                _("No active, approved WhatsApp template is configured.")
            )

        template_name = template.name
        language = template.language

        if not token or not phone_number_id:
            return mark_failed(_("Meta API credentials are missing."))

        if not recipient:
            return mark_failed(_("Recipient phone number is missing."))

        # Supply a full international number, without a leading plus sign.
        phone = "".join(char for char in recipient if char.isdigit())
        if not phone or len(phone) < 8:
            return mark_failed(_("Recipient phone number is invalid."))

        url = (
            f"https://graph.facebook.com/{api_version}/"
            f"{phone_number_id}/messages"
        )
        # payload = {
        #     "messaging_product": "whatsapp",
        #     "recipient_type": "individual",
        #     "to": phone,
        #     "type": "template",
        #     "template": {
        #         "name": template_name,
        #         "language": {"code": language},
        #         "components": [{
        #             "type": "body",
        #             "parameters": [
        #                 {"type": "text", "text": str(value or "-")}
        #                 for value in parameters
        #             ],
        #         }],
        #     },
        # }

        message = (
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

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message,
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

            print("Payload",payload)
            print("Response",response.json())

            try:
                result = response.json()
            except ValueError:
                result = {"error": response.text}

            if not response.ok:
                error = result.get("error", result)
                return mark_failed(error)

            messages = result.get("messages") or []
            message_id = messages[0].get("id") if messages else False

            if not message_id:
                return mark_failed(
                    _("Meta response did not contain a message ID: %s") % result
                )

            log.write({
                "status": "sent",
                "meta_message_id": message_id,
                "sent_at": fields.Datetime.now(),
                "error_details": False,
            })

            return result

        except requests.RequestException as error:
            _logger.exception("WhatsApp API request failed.")
            return mark_failed(error)

    def _notify_whatsapp_task(self, event="assigned"):
        ICP = self.env["ir.config_parameter"].sudo()

        for task in self:
            task_type = (
                "housekeeping"
                if task._name == "hotel.housekeeping"
                else "maintenance"
            )

            config_key = (
                f"vs_hotel_management.whatsapp_"
                f"{task_type}_{event}"
            )

            if ICP.get_param(config_key, "False").lower() not in (
                "true", "1", "yes"
            ):
                continue

            partner = task.assigned_to.partner_id
            phone = partner.mobile or partner.phone

            if not phone:
                _logger.warning(
                    "WhatsApp skipped for task %s: "
                    "the assigned employee has no phone number.",
                    task.display_name,
                )
                continue

            # Meta expects the recipient number in international format.
            recipient = "".join(
                char for char in phone if char.isdigit()
            )

            room = task.room_id
            hotel = getattr(task, "hotel_id", False)
            if not hotel and room:
                hotel = getattr(room, "hotel_id", False)

            detail_field = (
                "housekeeping_type"
                if task_type == "housekeeping"
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
            status = dict(
                task._fields["state"].selection
            ).get(task.state, task.state)

            base_url = ICP.get_param("web.base.url", "").rstrip("/")
            task_url = (
                f"{base_url}/web#id={task.id}"
                f"&model={task._name}&view_type=form"
            )

            parameters = [
                hotel.name if hotel else _("Hotel"),
                building.name if building else _("Not specified"),
                floor.name if floor else _("Not specified"),
                room.display_name if room else _("Not specified"),
                _("Housekeeping Type")
                if task_type == "housekeeping"
                else _("Maintenance Type"),
                detail,
                scheduled,
                status,
                getattr(task, "instruction_notes", False)
                or _("No additional instructions"),
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
                    "message": (
                        f"{task_type.title()} task {event}. "
                        f"Room: {room.display_name if room else '-'}"
                    ),
                },
            )

