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

    commission_ids = fields.One2many(
        "hotel.agent.commission",
        "folio_id",
        string="Agent Commissions",
    )

    commission_count = fields.Integer(
        string="Agent Commission Count",
        compute="_compute_commission_count",
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

    room_line_ids = fields.One2many(
        "hotel.guest.folio.line",
        "folio_id",
        domain=[("charge_type", "=", "room")],
        string="Room Charges",
    )

    service_line_ids = fields.One2many(
        "hotel.guest.folio.line",
        "folio_id",
        domain=[("charge_type", "=", "service")],
        string="Service Charges",
    )

    other_line_ids = fields.One2many(
        "hotel.guest.folio.line",
        "folio_id",
        domain=[("charge_type", "not in", ("room", "service"))],
        string="Other Charges",
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
        related="invoice_id.amount_total",
        currency_field="currency_id",
        store=True,
        readonly=True,
    )

    invoice_state = fields.Selection(
        related="invoice_id.payment_state",
        string="Invoice Payment Status",
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
            currency = folio.currency_id or self.env.company.currency_id
            charge_lines = folio.line_ids.filtered(lambda l: l.charge_type != "payment")
            payment_lines = folio.line_ids.filtered(lambda l: l.charge_type == "payment")

            raw_untaxed = sum(charge_lines.mapped("amount_untaxed"))
            raw_tax = sum(charge_lines.mapped("tax_amount"))
            raw_discount = sum(charge_lines.mapped("discount_amount"))
            raw_total = sum(charge_lines.mapped("total_amount"))

            folio.amount_untaxed = currency.round(raw_untaxed) if currency else raw_untaxed
            folio.tax_amount = currency.round(raw_tax) if currency else raw_tax
            folio.discount_amount = currency.round(raw_discount) if currency else raw_discount
            folio.total_amount = currency.round(raw_total) if currency else raw_total

            # High-accuracy invoice reconciliation
            if folio.invoice_id and folio.invoice_id.state == "posted":
                inv = folio.invoice_id
                inv_total = inv.amount_total
                inv_residual = inv.amount_residual
                is_inv_paid = (
                    inv.payment_state in ("paid", "in_payment")
                    or (currency and currency.is_zero(inv_residual))
                    or inv_residual <= 0.005
                )

                if is_inv_paid:
                    # Invoice is fully paid -> folio balance is exactly 0.0
                    folio.paid_amount = folio.total_amount
                    folio.balance_amount = 0.0
                elif inv.payment_state == "partial" or (inv_total > inv_residual > 0):
                    # Invoice is partially paid -> track paid amount accurately
                    inv_paid_amount = inv_total - inv_residual
                    folio.paid_amount = currency.round(min(folio.total_amount, max(0.0, inv_paid_amount))) if currency else min(folio.total_amount, max(0.0, inv_paid_amount))
                    raw_bal = folio.total_amount - folio.paid_amount
                    if (currency and currency.is_zero(raw_bal)) or raw_bal <= 0.005:
                        folio.balance_amount = 0.0
                    else:
                        folio.balance_amount = currency.round(raw_bal) if currency else raw_bal
                else:
                    folio.paid_amount = 0.0
                    folio.balance_amount = folio.total_amount
            else:
                line_paid = sum(payment_lines.mapped("total_amount")) or sum(folio.line_ids.mapped("paid_amount"))
                folio.paid_amount = currency.round(line_paid) if currency else line_paid
                raw_bal = folio.total_amount - folio.paid_amount
                if (currency and currency.is_zero(raw_bal)) or raw_bal <= 0.005:
                    folio.balance_amount = 0.0
                else:
                    folio.balance_amount = currency.round(max(0.0, raw_bal)) if currency else max(0.0, raw_bal)

            folio._sync_folio_payment_state()

    def _sync_folio_payment_state(self):
        """
        Synchronize folio status with payment amounts:
        - If invoice or balance is fully paid -> automatically 'paid'
        - If partially paid -> automatically 'partially_paid'
        - If no payment is made and state was partially_paid/paid -> return to 'open'
        - Closed and Cancelled folios remain untouched.
        """
        for folio in self:
            if folio.state in ("closed", "cancelled"):
                continue

            # Do not auto-pay or alter draft folios that have not received any payment
            if folio.state == "draft" and folio.paid_amount <= 0.001:
                continue

            currency = folio.currency_id or self.env.company.currency_id
            is_balance_zero = (
                (currency.is_zero(folio.balance_amount) if currency else folio.balance_amount <= 0.005)
            )
            is_inv_paid = bool(
                folio.invoice_id
                and folio.invoice_id.state == "posted"
                and (
                    folio.invoice_id.payment_state in ("paid", "in_payment")
                    or (currency and currency.is_zero(folio.invoice_id.amount_residual))
                    or folio.invoice_id.amount_residual <= 0.005
                )
            )
            is_inv_partial = bool(
                folio.invoice_id
                and folio.invoice_id.state == "posted"
                and folio.invoice_id.payment_state == "partial"
            )

            # 1. Fully Paid:
            if is_inv_paid or (is_balance_zero and (folio.paid_amount > 0.001 or folio.total_amount <= 0.001)):
                if folio.state != "paid":
                    folio.state = "paid"

            # 2. Partially Paid:
            elif is_inv_partial or (folio.paid_amount > 0.001 and not is_balance_zero):
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

    @api.model
    def get_active_folio_for_room(self, room_id):
        """
        Public Integration Hook for Future Addons (Restaurant POS, Laundry, Spa, Transport):
        Find the currently active open folio for a given room.
        :param room_id: hotel.room record or integer ID
        :return: hotel.guest.folio record (single record or empty recordset)
        """
        r_id = room_id.id if hasattr(room_id, "id") else room_id
        if not r_id:
            return self.browse()

        # 1. Search by open/draft/partially_paid folio on active reservation occupying or confirmed for this room
        folio = self.search([
            ("reservation_id.line_ids.room_id", "=", r_id),
            ("state", "in", ("draft", "open", "partially_paid")),
            ("reservation_id.state", "in", ("check_in", "confirmed")),
        ], limit=1, order="id desc")
        if folio:
            return folio

        # 2. Search by active room booking
        booking = self.env["hotel.room.booking"].search([
            ("room_id", "=", r_id),
            ("state", "in", ("confirmed", "check_in")),
            ("reservation_id.state", "in", ("confirmed", "check_in")),
        ], limit=1, order="id desc")
        if booking and booking.reservation_id:
            active_folios = booking.reservation_id.folio_ids.filtered(
                lambda f: f.state in ("draft", "open", "partially_paid")
            )
            if active_folios:
                return active_folios[:1]

        return self.browse()

    @api.model
    def get_active_folio_for_guest(self, partner_id, hotel_id=None):
        """
        Public Integration Hook for Future Addons:
        Find the currently active open folio for a given guest/partner.
        :param partner_id: res.partner record or integer ID
        :param hotel_id: optional hotel.hotel record or integer ID
        :return: hotel.guest.folio record (single record or empty recordset)
        """
        p_id = partner_id.id if hasattr(partner_id, "id") else partner_id
        if not p_id:
            return self.browse()

        domain = [
            ("partner_id", "=", p_id),
            ("state", "in", ("draft", "open", "partially_paid")),
        ]
        if hotel_id:
            h_id = hotel_id.id if hasattr(hotel_id, "id") else hotel_id
            domain.append(("hotel_id", "=", h_id))

        return self.search(domain, limit=1, order="id desc")

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

    @api.depends("commission_ids", "commission_ids.state")
    def _compute_commission_count(self):
        for folio in self:
            folio.commission_count = len(folio.commission_ids.filtered(lambda c: c.state != "cancelled"))

    def action_view_agent_commission(self):
        self.ensure_one()
        commissions = self.commission_ids.filtered(lambda c: c.state != "cancelled")
        if not commissions and self.reservation_id:
            commissions = self.reservation_id.commission_ids.filtered(lambda c: c.state != "cancelled")
        if not commissions:
            raise UserError(_("No commission record found for this folio."))
        if len(commissions) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Agent Commission"),
                "res_model": "hotel.agent.commission",
                "view_mode": "form",
                "res_id": commissions.id,
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Agent Commissions"),
            "res_model": "hotel.agent.commission",
            "view_mode": "list,form",
            "domain": [("id", "in", commissions.ids)],
        }

    def _auto_create_agent_commission(self):
        """
        Create agent commission record and per-room lines when a folio is checked out
        or invoice is paid. Delegates to the reservation's commission creator.
        """
        for folio in self:
            if folio.reservation_id and folio.reservation_id.booking_source == "travel_agent":
                folio.reservation_id._create_agent_commission_record(folio=folio)

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
                # Auto-create agent commissions when invoice becomes fully paid
                for folio in folios:
                    if folio.invoice_id and folio.invoice_id.payment_state in ("paid", "in_payment"):
                        folio._auto_create_agent_commission()
        return res

    def _compute_payment_state(self):
        super()._compute_payment_state()
        Folio = self.env["hotel.guest.folio"].sudo()
        folios = Folio.search([("invoice_id", "in", self.ids)])
        if folios:
            folios._compute_amounts()
            folios._sync_folio_payment_state()