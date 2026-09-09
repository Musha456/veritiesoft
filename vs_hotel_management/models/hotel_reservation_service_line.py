from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HotelReservationServiceLine(models.Model):
    _name = "hotel.reservation.service.line"
    _description = "Reservation Service Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)

    reservation_line_id = fields.Many2one(
        "hotel.reservation.line",
        string="Reservation Line",
        required=True,
        ondelete="cascade",
        index=True,
    )

    service_id = fields.Many2one(
        "hotel.service",
        string="Service",
        required=True,
        ondelete="restrict",
    )

    serve_date = fields.Datetime(
        string="Service Date",
        default=fields.Datetime.now,
        tracking=True,
    )

    quantity = fields.Float(
        string="Quantity",
        default=1.0,
        required=True,
    )

    price_unit = fields.Monetary(
        string="Unit Price",
        required=True,
        currency_field="currency_id",
    )

    discount_id = fields.Many2one(
        "hotel.discount",
        string="Discount",
    )

    discount_amount = fields.Monetary(
        string="Discount",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    tax_ids = fields.Many2many(
        "account.tax",
        string="Taxes",
    )

    tax_amount = fields.Monetary(
        string="Tax",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    subtotal = fields.Monetary(
        string="Subtotal",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    total = fields.Monetary(
        string="Total",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )

    currency_id = fields.Many2one(
        "res.currency",
        related="reservation_line_id.currency_id",
        store=True,
        readonly=True,
    )

    note = fields.Text(
        string="Note",
    )

    @api.onchange("service_id")
    def _onchange_service_id(self):
        for line in self:

            if not line.service_id:
                line.price_unit = 0.0
                line.tax_ids = False
                continue

            service = line.service_id

            line.price_unit = service.price

            if hasattr(service, "tax_ids"):
                line.tax_ids = service.tax_ids

    @api.onchange("quantity")
    def _onchange_quantity(self):
        for line in self:
            if line.quantity < 0:
                line.quantity = 0.0

    @api.constrains("quantity")
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(
                    _("Service quantity must be greater than zero.")
                )

    @api.depends(
        "quantity",
        "price_unit",
        "discount_id",
        "tax_ids",
    )
    def _compute_amounts(self):
        for line in self:

            gross_amount = (
                line.quantity * line.price_unit
            )

            # Discount
            discount_amount = 0.0

            if line.discount_id:
                discount = line.discount_id

                # Adapt these field names to your
                # hotel.discount model.
                if discount.discount_type == "percentage":
                    discount_amount = (
                        gross_amount
                        * discount.discount
                        / 100
                    )
                else:
                    discount_amount = discount.discount

                discount_amount = min(
                    discount_amount,
                    gross_amount,
                )

            line.discount_amount = discount_amount

            line.subtotal = (
                gross_amount - discount_amount
            )

            # Taxes
            tax_amount = 0.0

            if line.tax_ids:
                taxes = line.tax_ids.compute_all(
                    line.subtotal,
                    currency=line.currency_id,
                    quantity=1.0,
                    product=False,
                    partner=(
                        line.reservation_line_id
                        .reservation_id
                        .partner_id
                    ),
                )

                tax_amount = taxes["total_included"] - taxes[
                    "total_excluded"
                ]

            line.tax_amount = tax_amount
            line.total = line.subtotal + tax_amount

    # _sql_constraints = [
    #     (
    #         "reservation_line_service_unique",
    #         "unique(reservation_line_id, service_id)",
    #         "The same service cannot be added twice to the same room reservation.",
    #     ),
    # ]