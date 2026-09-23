from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_hotel_service = fields.Boolean(
        string="Hotel Service",
        default=False,
        tracking=True,
    )

    is_complimentary = fields.Boolean(
        string="Free Service",
        default=False,
        tracking=True,
    )

    hotel_description = fields.Html(
        string="Service Description",
        translate=True,
    )

    hotel_id = fields.Many2one(
        "hotel.hotel",
        string="Hotel",
        ondelete="set null",
        index=True,
    )

    reservation_id = fields.Many2one(
        "hotel.reservation",
        string="Reservation",
        ondelete="set null",
        index=True,
    )

    @api.onchange("is_complimentary")
    def _onchange_is_complimentary(self):
        for product in self:
            if product.is_complimentary:
                product.list_price = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("is_complimentary"):
                vals["list_price"] = 0.0
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("is_complimentary"):
            vals["list_price"] = 0.0
        return super().write(vals)