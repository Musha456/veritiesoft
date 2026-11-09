import re
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class HotelWhatsAppComposer(models.TransientModel):
    _name = "hotel.whatsapp.composer"
    _description = "Send WhatsApp Message"

    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
    )
    phone_number = fields.Char(
        string="Mobile / WhatsApp Number",
        required=True,
        help="Recipient's mobile number including country code (e.g. +1234567890).",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    template_id = fields.Many2one(
        "hotel.whatsapp.template",
        string="WhatsApp Template",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id), ('meta_status', '=', 'approved')]",
        help="Select a template to auto-populate the message, or leave blank to write a custom text.",
    )
    message = fields.Text(
        string="Message",
        required=True,
        help="Message body to be sent via WhatsApp.",
    )
    template_preview = fields.Text(
        string="Template Preview",
        compute="_compute_template_preview",
        store=False,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get("active_model")
        active_id = self.env.context.get("active_id")

        if active_model == "res.partner" and active_id:
            partner = self.env["res.partner"].browse(active_id)
            if partner.exists():
                res["partner_id"] = partner.id
                res["phone_number"] = (getattr(partner, "mobile", False) or partner.phone or "")
                if partner.company_id:
                    res["company_id"] = partner.company_id.id

        return res

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            self.phone_number = (getattr(self.partner_id, "mobile", False) or self.partner_id.phone or "")
            if self.partner_id.company_id:
                self.company_id = self.partner_id.company_id.id
            if self.template_id:
                self._apply_template()

    @api.onchange("template_id")
    def _onchange_template_id(self):
        self._apply_template()

    @api.depends("template_id", "partner_id")
    def _compute_template_preview(self):
        for rec in self:
            rec.template_preview = rec._render_template_text()

    def _render_template_text(self):
        if not self.template_id or not self.template_id.body_text:
            return ""
        text = self.template_id.body_text
        partner_name = self.partner_id.name or _("Valued Guest")
        company_name = self.company_id.name or self.env.company.name

        text = re.sub(r"\{\{1\}\}", partner_name, text)
        text = re.sub(r"\{\{2\}\}", company_name, text)
        return text

    def _apply_template(self):
        if self.template_id and self.template_id.body_text:
            rendered = self._render_template_text()
            self.message = rendered

    def action_send_whatsapp(self):
        self.ensure_one()
        if not self.phone_number:
            raise UserError(_("Please provide a valid WhatsApp / Mobile number."))
        if not self.message or not self.message.strip():
            raise UserError(_("Message content cannot be empty."))

        digits_phone = "".join(ch for ch in str(self.phone_number) if ch.isdigit() or ch == "+")

        task_type = "other"
        event = "other"
        if self.template_id:
            if self.template_id.task_type in ("housekeeping", "maintenance", "reservation", "folio"):
                task_type = self.template_id.task_type
            if self.template_id.event and self.template_id.event != "both":
                event = self.template_id.event

        log = self.env["hotel.whatsapp.log"].create({
            "recipient_id": self.partner_id.id,
            "phone_number": digits_phone,
            "message": self.message,
            "company_id": self.company_id.id,
            "task_type": task_type,
            "event": event,
            "status": "queued",
        })

        # Attempt immediate dispatch if gateway credentials are setup
        try:
            log._send_meta_whatsapp_message()
        except Exception as exc:
            _logger.warning("WhatsApp send exception for partner %s: %s", self.partner_id.display_name, exc)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("WhatsApp Notification"),
                "message": _("WhatsApp message for '%(partner)s' has been queued successfully.") % {
                    "partner": self.partner_id.display_name,
                },
                "type": "success",
                "sticky": False,
            },
        }
