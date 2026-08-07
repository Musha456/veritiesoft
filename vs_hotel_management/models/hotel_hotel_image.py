from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HotelHotelImage(models.Model):
    _name = "hotel.hotel.image"
    _description = "Hotel Image"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, id"
    _rec_name = "name"
    _check_company_auto = True

    sequence = fields.Integer(
        default=10,
    )

    active = fields.Boolean(
        default=True,
        tracking=True,
    )

    name = fields.Char(
        string="Title",
        required=True,
        translate=True,
        tracking=True,
    )

    hotel_id = fields.Many2one(
        "hotel.hotel",
        string="Hotel",
        required=True,
        ondelete="cascade",
        check_company=True,
        index=True,
    )

    image = fields.Image(
        string="Image",
        required=True,
        max_width=1920,
        max_height=1080,
    )

    is_cover = fields.Boolean(
        string="Cover Image",
        tracking=True,
        help="Used as the main image on the website and booking pages.",
    )

    description = fields.Text(
        translate=True,
    )

    company_id = fields.Many2one(
        "res.company",
        related="hotel_id.company_id",
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            "hotel_image_name_unique",
            "unique(hotel_id, name)",
            "The image title must be unique per hotel.",
        ),
    ]

    # @api.constrains("is_cover", "hotel_id")
    # def _check_single_cover(self):
    #     for record in self.filtered("is_cover"):
    #         if self.search_count([
    #             ("hotel_id", "=", record.hotel_id.id),
    #             ("is_cover", "=", True),
    #             ("id", "!=", record.id),
    #         ]):
    #             raise ValidationError(
    #                 "Only one cover image is allowed per hotel."
    #             )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for record in records:
            hotel = record.hotel_id

            if len(hotel.image_ids) == 1:
                record.is_cover = True

            elif record.is_cover:
                (hotel.image_ids - record).write({
                    "is_cover": False,
                })

        return records

    def write(self, vals):
        res = super().write(vals)

        for hotel in self.mapped("hotel_id"):

            covers = hotel.image_ids.filtered("is_cover")

            if len(covers) > 1:
                current = self.filtered(
                    lambda r: r.hotel_id == hotel and r.is_cover
                )[:1]

                if current:
                    (covers - current).write({
                        "is_cover": False,
                    })

            elif not covers and hotel.image_ids:
                hotel.image_ids.sorted("sequence")[0].is_cover = True

        return res

    def unlink(self):
        hotels = self.mapped("hotel_id")

        res = super().unlink()

        for hotel in hotels:
            if hotel.image_ids and not hotel.image_ids.filtered("is_cover"):
                hotel.image_ids.sorted("sequence")[0].is_cover = True

        return res