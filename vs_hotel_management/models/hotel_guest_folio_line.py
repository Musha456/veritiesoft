from odoo import api, fields, models, _
from odoo.exceptions import UserError

class HotelGuestFolioLine(models.Model):
    _name = "hotel.guest.folio.line"
    _description = "Guest Folio Line"
    _order = "date desc, id desc"

    folio_id = fields.Many2one(
        "hotel.guest.folio",
        string="Folio",
        required=True,
        ondelete="cascade",
        index=True,
    )

    date = fields.Datetime(
        string="Date",
        required=True,
        default=fields.Datetime.now,
    )

    description = fields.Char(
        string="Description",
        required=True,
    )

    charge_type = fields.Selection(
        [
            ("room", "Room"),
            ("service", "Service"),
            ("restaurant", "Restaurant"),
            ("laundry", "Laundry"),
            ("minibar", "Minibar"),
            ("extra", "Extra"),
            ("discount", "Discount"),
            ("tax", "Tax"),
            ("payment", "Payment"),
            ("other", "Other"),
        ],
        string="Charge Type",
        required=True,
        default="other",
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        check_company=True,
        domain="[('sale_ok', '=', True), ('company_id', '=', company_id)]",
    )

    tax_ids = fields.Many2many(
        "account.tax",
        string="Taxes",
    )

    invoice_line_id = fields.Many2one(
        "account.move.line",
        string="Invoice Line",
        readonly=True,
        ondelete="set null",
        index=True,
    )

    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        related="invoice_line_id.move_id",
        store=True,
        readonly=True,
    )

    quantity = fields.Float(
        string="Quantity",
        default=1.0,
    )

    unit_price = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
    )

    discount = fields.Float(
        string="Discount (%)",
        default=0.0,
    )

    amount_untaxed = fields.Monetary(
        string="Untaxed Amount",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    discount_amount = fields.Monetary(
        string="Discount Amount",
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

    total_amount = fields.Monetary(
        string="Total",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    paid_amount = fields.Monetary(
        string="Paid",
        default=0.0,
        currency_field="currency_id",
    )

    currency_id = fields.Many2one(
        "res.currency",
        related="folio_id.currency_id",
        store=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        "res.company",
        related="folio_id.company_id",
        store=True,
        readonly=True,
    )

    reservation_line_id = fields.Many2one(
        "hotel.reservation.line",
        string="Reservation Line",
        ondelete="restrict",
        index=True,
    )

    reservation_service_line_id = fields.Many2one(
        "hotel.reservation.service.line",
        string="Reservation Service Line",
        ondelete="restrict",
        index=True,
    )

    room_booking_id = fields.Many2one(
        "hotel.room.booking",
        string="Room Booking",
        ondelete="restrict",
        index=True,
    )

    source_amount = fields.Monetary(
        string="Source Amount",
        currency_field="currency_id",
    )

    @api.depends(
        "quantity",
        "unit_price",
        "discount",
        "tax_ids",
    )
    def _compute_amounts(self):
        for line in self:
            gross = line.quantity * line.unit_price

            discount_amount = (
                    gross * (line.discount / 100.0)
            )

            amount_untaxed = gross - discount_amount

            tax_amount = 0.0

            if line.tax_ids and amount_untaxed > 0:
                taxes = line.tax_ids.compute_all(
                    amount_untaxed,
                    currency=line.currency_id,
                    quantity=1.0,
                    product=False,
                    partner=line.folio_id.partner_id,
                )

                tax_amount = (
                        taxes["total_included"]
                        - taxes["total_excluded"]
                )

            line.discount_amount = discount_amount
            line.amount_untaxed = amount_untaxed
            line.tax_amount = tax_amount
            line.total_amount = (
                    amount_untaxed + tax_amount
            )