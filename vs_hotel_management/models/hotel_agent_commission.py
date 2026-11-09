# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HotelAgentCommission(models.Model):
    """
    Travel Agent Commission Management (Folio-Style).

    A commission record tracks payable commission to a travel agent for a
    reservation/folio checkout. Contains detailed per-room commission lines
    and provides one-click or automated vendor bill generation.
    """
    _name = "hotel.agent.commission"
    _description = "Travel Agent Commission"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Commission Reference",
        required=True,
        readonly=True,
        copy=False,
        default="/",
        index=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("billed", "Billed"),
            ("paid", "Paid"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )

    agent_id = fields.Many2one(
        "res.partner",
        string="Travel Agent",
        required=True,
        domain="[('is_travel_agent', '=', True)]",
        tracking=True,
        index=True,
    )

    reservation_id = fields.Many2one(
        "hotel.reservation",
        string="Reservation",
        tracking=True,
        ondelete="set null",
        index=True,
    )

    folio_id = fields.Many2one(
        "hotel.guest.folio",
        string="Guest Folio",
        tracking=True,
        ondelete="set null",
        index=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    date = fields.Date(
        string="Commission Date",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )

    commission_line_ids = fields.One2many(
        "hotel.agent.commission.line",
        "commission_id",
        string="Room Commission Lines",
        copy=True,
    )

    total_base_amount = fields.Monetary(
        string="Total Base Amount",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
        help="Total gross/undiscounted room charges.",
    )

    total_discount_amount = fields.Monetary(
        string="Total Discount Amount",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
        help="Total room discounts applied.",
    )

    total_room_amount = fields.Monetary(
        string="Total Net Room Amount",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
        help="Total room charges after discount on which commission is calculated.",
    )

    total_commission_amount = fields.Monetary(
        string="Total Commission",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
        help="Total payable commission amount owed to the travel agent.",
    )

    invoice_id = fields.Many2one(
        "account.move",
        string="Vendor Bill",
        readonly=True,
        copy=False,
        help="Vendor bill (AP) generated to pay this agent commission.",
    )

    payment_state = fields.Selection(
        related="invoice_id.payment_state",
        string="Bill Payment State",
        store=True,
        readonly=True,
    )

    commission_email_sent = fields.Boolean(
        string="Statement Email Sent",
        default=False,
        readonly=True,
        copy=False,
        help="Indicates whether the commission statement email has been sent to the travel agent.",
    )

    notes = fields.Text(
        string="Notes",
    )

    @api.depends(
        "commission_line_ids",
        "commission_line_ids.base_amount",
        "commission_line_ids.discount_amount",
        "commission_line_ids.room_amount",
        "commission_line_ids.commission_amount",
    )
    def _compute_totals(self):
        for record in self:
            record.total_base_amount = sum(record.commission_line_ids.mapped("base_amount"))
            record.total_discount_amount = sum(record.commission_line_ids.mapped("discount_amount"))
            record.total_room_amount = sum(record.commission_line_ids.mapped("room_amount"))
            record.total_commission_amount = sum(record.commission_line_ids.mapped("commission_amount"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("hotel.agent.commission") or "/"
                )
        return super().create(vals_list)

    def action_confirm(self):
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only draft commission records can be confirmed."))
            record.state = "confirmed"

    def action_bill(self):
        """Mark commission as billed."""
        for record in self:
            if record.state not in ("confirmed", "draft"):
                raise UserError(_("Only confirmed or draft commission records can be billed."))
            record.state = "billed"

    def action_mark_paid(self):
        for record in self:
            if record.state not in ("confirmed", "billed"):
                raise UserError(_("Only confirmed or billed commission records can be marked as paid."))
            record.state = "paid"
            auto_send = self.env["ir.config_parameter"].sudo().get_param(
                "vs_hotel_management.auto_send_agent_commission_email", default="True"
            )
            if auto_send in (True, "True", "1", 1) and not record.commission_email_sent:
                record._send_commission_paid_email()

    def action_cancel(self):
        for record in self:
            if record.state == "paid":
                raise UserError(_("Paid commission records cannot be cancelled."))
            if record.invoice_id and record.invoice_id.state != "cancel":
                raise UserError(_("Cancel or unlink the linked vendor bill before cancelling this commission."))
            record.state = "cancelled"

    def action_reset_to_draft(self):
        for record in self:
            if record.state not in ("confirmed", "cancelled"):
                raise UserError(_("Only confirmed or cancelled records can be reset to draft."))
            record.state = "draft"

    def action_create_vendor_bill(self):
        """Create a vendor bill (AP) for the travel agent commission."""
        self.ensure_one()
        if self.state == "cancelled":
            raise UserError(_("Cannot create a bill for a cancelled commission record."))

        if self.invoice_id:
            return self.action_view_bill()

        if not self.commission_line_ids:
            raise UserError(_("Cannot create a vendor bill without commission lines."))

        invoice_lines = []
        for line in self.commission_line_ids:
            room_desc = line.room_id.display_name if line.room_id else (line.room_name or _("Room"))
            res_ref = line.reservation_id.name if line.reservation_id else (self.reservation_id.name if self.reservation_id else "-")
            description = _(
                "Travel Agent Commission: %(res)s | %(room)s | Base: %(base).2f | Disc: %(disc).2f | Net: %(net).2f | %(pct).2f%%"
            ) % {
                "res": res_ref,
                "room": room_desc,
                "base": line.base_amount,
                "disc": line.discount_amount,
                "net": line.room_amount,
                "pct": line.commission_percentage,
            }
            invoice_lines.append((0, 0, {
                "name": description,
                "quantity": 1.0,
                "price_unit": line.commission_amount,
            }))

        bill_ref = f"{self.name} - {self.reservation_id.name if self.reservation_id else ''}".strip(" -")
        bill = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.agent_id.id,
            "invoice_date": fields.Date.context_today(self),
            "currency_id": self.currency_id.id,
            "invoice_origin": self.name,
            "ref": bill_ref,
            "invoice_line_ids": invoice_lines,
        })

        self.invoice_id = bill.id
        self.state = "billed"

        return self.action_view_bill()

    def action_view_bill(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No vendor bill has been created for this commission."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Commission Bill"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.invoice_id.id,
        }

    def action_view_reservation(self):
        self.ensure_one()
        if not self.reservation_id:
            raise UserError(_("No reservation linked to this commission."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Reservation"),
            "res_model": "hotel.reservation",
            "view_mode": "form",
            "res_id": self.reservation_id.id,
        }

    def action_view_folio(self):
        self.ensure_one()
        if not self.folio_id:
            raise UserError(_("No guest folio linked to this commission."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Guest Folio"),
            "res_model": "hotel.guest.folio",
            "view_mode": "form",
            "res_id": self.folio_id.id,
        }

    def action_print_commission_report(self):
        """Print the Travel Agent Commission Statement PDF report."""
        self.ensure_one()
        return self.env.ref("vs_hotel_management.action_report_hotel_agent_commission").report_action(self)

    def action_send_commission_email(self):
        """Open composer wizard to manually review and send the commission email."""
        self.ensure_one()
        template = self.env.ref("vs_hotel_management.mail_template_hotel_agent_commission", raise_if_not_found=False)
        compose_form = self.env.ref("mail.email_compose_message_wizard_form", raise_if_not_found=False)
        ctx = {
            "default_model": "hotel.agent.commission",
            "default_res_ids": [self.id],
            "default_template_id": template.id if template else False,
            "default_composition_mode": "comment",
            "force_email": True,
        }
        return {
            "name": _("Send Commission Statement"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "views": [(compose_form.id if compose_form else False, "form")],
            "view_id": compose_form.id if compose_form else False,
            "target": "new",
            "context": ctx,
        }

    def _send_commission_paid_email(self):
        """
        Sends the agent commission email with the commission statement PDF
        and paid vendor bill PDF attached.
        """
        template = self.env.ref("vs_hotel_management.mail_template_hotel_agent_commission", raise_if_not_found=False)
        if not template:
            _logger.warning("Agent commission mail template 'mail_template_hotel_agent_commission' not found.")
            return

        for record in self:
            if not record.agent_id.email:
                _logger.info("Agent %s has no email address configured. Skipping commission email.", record.agent_id.name)
                record.message_post(
                    body=_("Could not send commission email: Travel Agent %(agent)s has no email address.") % {
                        "agent": record.agent_id.name,
                    }
                )
                continue

            attachment_ids = []
            # Attach the Vendor Bill PDF if available
            if record.invoice_id:
                try:
                    bill_report = self.env.ref("account.account_invoices", raise_if_not_found=False)
                    if bill_report:
                        bill_pdf, _ext = self.env["ir.actions.report"]._render_qweb_pdf(bill_report, [record.invoice_id.id])
                        if bill_pdf:
                            bill_name = f"Bill_{record.invoice_id.name.replace('/', '_')}.pdf" if record.invoice_id.name else "Vendor_Bill.pdf"
                            bill_att = self.env["ir.attachment"].create({
                                "name": bill_name,
                                "type": "binary",
                                "raw": bill_pdf,
                                "res_model": "hotel.agent.commission",
                                "res_id": record.id,
                                "mimetype": "application/pdf",
                            })
                            attachment_ids.append(bill_att.id)
                except Exception as e:
                    _logger.warning("Could not generate paid bill attachment: %s", e)

            email_values = {}
            if attachment_ids:
                email_values["attachment_ids"] = [(4, att_id) for att_id in attachment_ids]

            template.send_mail(
                record.id,
                force_send=True,
                raise_exception=False,
                email_values=email_values,
            )
            record.commission_email_sent = True
            bill_name = record.invoice_id.name or record.invoice_id.display_name or "Vendor Bill" if record.invoice_id else ""
            bill_info = f" with Vendor Bill ({bill_name})" if record.invoice_id else ""
            record.message_post(
                body=_("Commission statement%(bill_info)s successfully sent to %(agent)s (%(email)s).") % {
                    "bill_info": bill_info,
                    "agent": record.agent_id.name,
                    "email": record.agent_id.email,
                }
            )


class HotelAgentCommissionLine(models.Model):
    """
    Individual per-room commission line linked to a commission record.
    Displays base amount, discount, net room amount, commission percentage,
    and computed commission amount.
    """
    _name = "hotel.agent.commission.line"
    _description = "Agent Commission Line"
    _order = "date desc, id desc"

    commission_id = fields.Many2one(
        "hotel.agent.commission",
        string="Commission Record",
        required=True,
        ondelete="cascade",
        index=True,
    )

    currency_id = fields.Many2one(
        related="commission_id.currency_id",
        store=True,
        readonly=True,
    )

    date = fields.Date(
        string="Date",
        default=fields.Date.context_today,
        required=True,
    )

    reservation_id = fields.Many2one(
        "hotel.reservation",
        string="Reservation",
        ondelete="set null",
        index=True,
    )

    folio_id = fields.Many2one(
        "hotel.guest.folio",
        string="Guest Folio",
        ondelete="set null",
        index=True,
    )

    reservation_line_id = fields.Many2one(
        "hotel.reservation.line",
        string="Reservation Line",
        ondelete="set null",
        index=True,
    )

    room_booking_id = fields.Many2one(
        "hotel.room.booking",
        string="Room Booking",
        ondelete="set null",
        index=True,
    )

    room_id = fields.Many2one(
        "hotel.room",
        string="Room",
        ondelete="set null",
        index=True,
    )

    room_name = fields.Char(
        string="Room Name",
        help="Room identifier or number.",
    )

    night_count = fields.Float(
        string="Nights",
        default=1.0,
    )

    base_amount = fields.Monetary(
        string="Base Amount",
        currency_field="currency_id",
        help="Undiscounted gross room charges for this room.",
    )

    discount_amount = fields.Monetary(
        string="Discount",
        currency_field="currency_id",
        help="Discount amount applied to this room charge.",
    )

    room_amount = fields.Monetary(
        string="Net Room Amount",
        currency_field="currency_id",
        help="Room charge after discount on which commission is calculated.",
    )

    commission_percentage = fields.Float(
        string="Commission (%)",
        help="Commission percentage applied.",
    )

    commission_amount = fields.Monetary(
        string="Commission Amount",
        compute="_compute_commission_amount",
        store=True,
        readonly=False,
        currency_field="currency_id",
        help="Payable commission = room_amount (after discount) × commission_percentage / 100.",
    )

    notes = fields.Char(
        string="Description",
    )

    @api.depends("room_amount", "base_amount", "discount_amount", "commission_percentage")
    def _compute_commission_amount(self):
        for line in self:
            if not line.room_amount and line.base_amount:
                line.room_amount = max(line.base_amount - line.discount_amount, 0.0)
            if line.room_amount and line.commission_percentage:
                line.commission_amount = (line.room_amount * line.commission_percentage) / 100.0
            else:
                line.commission_amount = 0.0


class AccountMove(models.Model):
    _inherit = "account.move"

    def _compute_payment_state(self):
        super()._compute_payment_state()
        Commission = self.env["hotel.agent.commission"].sudo()
        auto_send = self.env["ir.config_parameter"].sudo().get_param(
            "vs_hotel_management.auto_send_agent_commission_email", default="True"
        )
        for move in self:
            if move.move_type == "in_invoice" and move.payment_state in ("paid", "in_payment"):
                commissions = Commission.search([("invoice_id", "=", move.id), ("state", "!=", "paid")])
                if commissions:
                    commissions.write({"state": "paid"})
                if auto_send in (True, "True", "1", 1):
                    all_comms = Commission.search([
                        ("invoice_id", "=", move.id),
                        ("commission_email_sent", "=", False),
                    ])
                    for comm in all_comms:
                        comm._send_commission_paid_email()
