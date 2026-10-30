from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HotelGuestFolio(models.Model):
    _name = "hotel.guest.folio"
    _description = "Hotel Guest Folio"
    _inherit = ["mail.thread", "mail.activity.mixin", "hotel.notification.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Folio Number",
        required=True,
        readonly=True,
        copy=False,
        default="/",
        index=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Guest",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        domain="[('is_hotel_guest', '=', True)]",
    )

    reservation_id = fields.Many2one(
        "hotel.reservation",
        string="Reservation",
        ondelete="restrict",
        index=True,
        tracking=True,
    )

    room_booking_id = fields.Many2one(
        "hotel.room.booking",
        string="Room Booking",
        ondelete="restrict",
        index=True,
    )

    hotel_id = fields.Many2one(
        "hotel.hotel",
        string="Hotel",
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

    check_in = fields.Datetime(
        string="Check-in",
    )

    check_out = fields.Datetime(
        string="Check-out",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("open", "Open"),
            ("partially_paid", "Partially Paid"),
            ("paid", "Paid"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )

    line_ids = fields.One2many(
        "hotel.guest.folio.line",
        "folio_id",
        string="Folio Lines",
    )

    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        readonly=True,
        copy=False,
        ondelete="set null",
        index=True,
    )

    amount_untaxed = fields.Monetary(
        string="Untaxed Amount",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    tax_amount = fields.Monetary(
        string="Tax",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    discount_amount = fields.Monetary(
        string="Discount",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    total_amount = fields.Monetary(
        string="Total",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    paid_amount = fields.Monetary(
        string="Paid",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    balance_amount = fields.Monetary(
        string="Balance",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    invoice_amount = fields.Monetary(
        string="Invoice Amount",
        compute="_compute_amounts",
        currency_field="currency_id",
        store=True,
    )

    invoice_state = fields.Selection(
        related="invoice_id.payment_state",
        string="Invoice Payment Status",
        readonly=True,
    )

    invoice_amount = fields.Monetary(
        string="Invoice Amount",
        related="invoice_id.amount_total",
        currency_field="currency_id",
        readonly=True,
    )

    notes = fields.Text(
        string="Notes",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("hotel.guest.folio")
                    or "/"
                )

        records = super().create(vals_list)

        for folio in records:
            folio._populate_from_reservation()

        return records

    @api.depends(
        "line_ids",
        "line_ids.amount_untaxed",
        "line_ids.tax_amount",
        "line_ids.discount_amount",
        "line_ids.total_amount",
        "line_ids.paid_amount",
        "invoice_id",
        "invoice_id.amount_total",
        "invoice_id.amount_residual",
        "invoice_id.payment_state",
        "invoice_id.state",
    )
    def _compute_amounts(self):
        for folio in self:
            charge_lines = folio.line_ids.filtered(lambda l: l.charge_type != "payment")
            payment_lines = folio.line_ids.filtered(lambda l: l.charge_type == "payment")

            folio.amount_untaxed = sum(charge_lines.mapped("amount_untaxed"))
            folio.tax_amount = sum(charge_lines.mapped("tax_amount"))
            folio.discount_amount = sum(charge_lines.mapped("discount_amount"))
            folio.total_amount = sum(charge_lines.mapped("total_amount"))

            invoice_paid = 0.0
            if folio.invoice_id and folio.invoice_id.state == "posted":
                invoice_paid = folio.invoice_id.amount_total - folio.invoice_id.amount_residual

            line_paid = sum(payment_lines.mapped("total_amount")) or sum(folio.line_ids.mapped("paid_amount"))
            folio.paid_amount = max(invoice_paid, line_paid)
            folio.balance_amount = max(0.0, folio.total_amount - folio.paid_amount)

            folio.invoice_amount = (
                folio.invoice_id.amount_total
                if folio.invoice_id
                else 0.0
            )

            folio._sync_folio_payment_state()

    def _sync_folio_payment_state(self):
        """
        Synchronize folio status with payment amounts:
        - If payment is partially made and balance is not zero -> 'partially_paid'
        - If balance is equal to zero (fully paid) -> automatically 'paid'
        - If no payment is made and state was partially_paid/paid -> return to 'open'
        - Closed and Cancelled folios remain untouched.
        """
        for folio in self:
            if folio.state in ("closed", "cancelled"):
                continue

            # Do not auto-pay or alter draft folios that have not received any payment
            if folio.state == "draft" and folio.paid_amount <= 0.001:
                continue

            # 1. Fully Paid: Balance is zero and either payment is made or folio has 0 total charges
            if folio.balance_amount <= 0.001 and (folio.paid_amount > 0.001 or folio.total_amount <= 0.001):
                if folio.state != "paid":
                    folio.state = "paid"

            # 2. Partially Paid: Payment received (> 0) and balance is not equal to zero (> 0)
            elif folio.paid_amount > 0.001 and folio.balance_amount > 0.001:
                if folio.state != "partially_paid":
                    folio.state = "partially_paid"

            # 3. No Payment: Return to 'open' if previously marked partially_paid or paid
            elif folio.paid_amount <= 0.001 and folio.state in ("partially_paid", "paid"):
                folio.state = "open"

    def _populate_from_reservation(self):
        for folio in self:
            reservation = folio.reservation_id

            if not reservation:
                continue

            folio.write({
                "partner_id": reservation.partner_id.id,
                "check_in": reservation.check_in,
                "check_out": reservation.check_out,
            })

    def action_open(self):
        for folio in self:
            if folio.state != "draft":
                raise UserError(
                    _("Only draft folios can be opened.")
                )

            folio.state = "open"

        return True

    def action_close(self):
        for folio in self:
            if folio.balance_amount > 0:
                raise UserError(
                    _(
                        "Folio %s cannot be closed while "
                        "an outstanding balance of %s remains."
                    )
                    % (
                        folio.display_name,
                        folio.balance_amount,
                    )
                )

            if folio.state not in ("open", "partially_paid", "paid"):
                raise UserError(
                    _("Only active folios can be closed.")
                )

            folio.state = "closed"

        return True

    def action_cancel(self):
        for folio in self:
            if folio.state == "closed":
                raise UserError(
                    _("Closed folios cannot be cancelled.")
                )
            if folio.reservation_id and folio.reservation_id.state in ("checked_in", "checked_out", "completed"):
                state_label = dict(folio.reservation_id._fields["state"].selection).get(
                    folio.reservation_id.state, folio.reservation_id.state
                )
                raise UserError(
                    _(
                        "Folio '%(folio)s' cannot be cancelled because it is linked to reservation '%(res)s' which is already %(state)s."
                    )
                    % {
                        "folio": folio.name,
                        "res": folio.reservation_id.name,
                        "state": state_label,
                    }
                )

            folio.state = "cancelled"

    def add_charge(
            self,
            description,
            charge_type="other",
            product=None,
            quantity=1.0,
            unit_price=0.0,
            discount=0.0,
            tax_ids=None,
            reservation_line=None,
            reservation_service_line=None,
            room_booking=None,
            **kwargs,
    ):
        self.ensure_one()

        vals = {
            "folio_id": self.id,
            "date": fields.Datetime.now(),
            "description": description,
            "charge_type": charge_type,
            "product_id": product.id if product else False,
            "reservation_line_id": reservation_line.id if reservation_line else False,
            "reservation_service_line_id": reservation_service_line.id if reservation_service_line else False,
            "room_booking_id": room_booking.id if room_booking else False,
            "quantity": quantity,
            "unit_price": unit_price,
            "discount": discount,
            "tax_ids": [(6, 0, tax_ids.ids)] if tax_ids else False,
        }
        for k, v in kwargs.items():
            if k in self.env["hotel.guest.folio.line"]._fields:
                vals[k] = v

        return self.env["hotel.guest.folio.line"].create(vals)

    def action_create_invoice(self):
        AccountMove = self.env["account.move"]

        for folio in self:
            if folio.invoice_id:
                raise UserError(
                    _("An invoice has already been created for folio %s.")
                    % folio.display_name
                )

            if folio.state == "cancelled":
                raise UserError(
                    _("A cancelled folio cannot be invoiced.")
                )

            if not folio.line_ids:
                raise UserError(
                    _("Cannot create an invoice without folio charges.")
                )

            invoice_lines = []

            for line in folio.line_ids.filtered(
                    lambda line: line.charge_type != "payment"
            ):
                if not line.product_id:
                    raise UserError(
                        _(
                            "Product is required for folio line '%s' "
                            "before creating the invoice."
                        )
                        % line.description
                    )

                invoice_lines.append(
                    (
                        0,
                        0,
                        {
                            "product_id": line.product_id.id,
                            "name": line.description,
                            "quantity": line.quantity,
                            "price_unit": line.unit_price,
                            "discount": line.discount,
                            "tax_ids": [(6, 0, line.tax_ids.ids)],
                        },
                    )
                )

            if not invoice_lines:
                raise UserError(
                    _("There are no invoiceable charges on folio %s.")
                    % folio.display_name
                )

            invoice = AccountMove.create({
                "move_type": "out_invoice",
                "partner_id": folio.partner_id.id,
                "invoice_date": fields.Date.context_today(self),
                "currency_id": folio.currency_id.id,
                "invoice_origin": folio.name,
                "ref": folio.name,
                "invoice_line_ids": invoice_lines,
            })

            folio.invoice_id = invoice.id

        return True

    def action_view_invoice(self):
        self.ensure_one()

        if not self.invoice_id:
            raise UserError(
                _("No invoice has been created for this folio.")
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Guest Invoice"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.invoice_id.id,
        }

    def action_send_folio_email(self):
        """Open email composer with guest folio template."""
        self.ensure_one()
        template = self.env.ref(
            "vs_hotel_management.mail_template_hotel_guest_folio",
            raise_if_not_found=False,
        )
        compose_form = self.env.ref(
            "mail.email_compose_message_wizard_form",
            raise_if_not_found=False,
        )
        ctx = {
            "default_model": "hotel.guest.folio",
            "default_res_ids": self.ids,
            "default_use_template": bool(template),
            "default_template_id": template.id if template else False,
            "default_composition_mode": "comment",
            "mark_so_as_sent": True,
            "force_email": True,
        }
        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "views": [(compose_form.id if compose_form else False, "form")],
            "view_id": compose_form.id if compose_form else False,
            "target": "new",
            "context": ctx,
        }

    def action_register_payment(self):
        """Open payment registration wizard linked with the folio's invoice."""
        self.ensure_one()
        if self.state in ("closed", "cancelled"):
            raise UserError(_("Cannot register payment on a closed or cancelled folio."))

        if not self.line_ids:
            raise UserError(_("Cannot register payment on a folio with no charges."))

        if self.state == "draft":
            self.action_open()

        if not self.invoice_id:
            self.action_create_invoice()

        if self.invoice_id.state == "draft":
            self.invoice_id.action_post()

        if self.invoice_id.payment_state in ("paid", "in_payment") or self.balance_amount <= 0:
            raise UserError(_("The invoice for this folio is already fully paid."))

        return {
            "name": _("Register Payment"),
            "type": "ir.actions.act_window",
            "res_model": "account.payment.register",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {
                "active_model": "account.move",
                "active_ids": [self.invoice_id.id],
            },
        }


class AccountMove(models.Model):
    _inherit = "account.move"

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in ("payment_state", "amount_residual", "state")):
            Folio = self.env["hotel.guest.folio"].sudo()
            folios = Folio.search([("invoice_id", "in", self.ids)])
            if folios:
                folios._compute_amounts()
                folios._sync_folio_payment_state()
        return res

    def _compute_payment_state(self):
        super()._compute_payment_state()
        Folio = self.env["hotel.guest.folio"].sudo()
        folios = Folio.search([("invoice_id", "in", self.ids)])
        if folios:
            folios._compute_amounts()
            folios._sync_folio_payment_state()