from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class HotelRoomCategory(models.Model):
    _name = "hotel.room.category"
    _description = "Hotel Room Category"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _rec_name = "name"

    name = fields.Char(
        string="Room Category",
        required=True,
        tracking=True,
    )

    code = fields.Char(
        string="Code",
        readonly=True,
        copy=False,
        default="/",
        tracking=True,
        index=True,
    )

    sequence = fields.Integer(default=10)

    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )

    image = fields.Image(
        max_width=1024,
        max_height=1024,
    )

    bed_type_id = fields.Many2one(
        "hotel.bed.type",
        required=True,
        ondelete="restrict",
    )

    bed_count = fields.Integer(
        default=1,
    )

    room_size = fields.Float(
        string="Room Size",
    )

    room_size_uom = fields.Selection(
        [
            ("sqm", "m²"),
            ("sqft", "ft²"),
        ],
        default="sqm",
    )

    max_adults = fields.Integer(
        default=2,
    )

    max_infants = fields.Integer(
        default=2,
    )

    max_children = fields.Integer(
        default=0,
    )

    max_occupancy = fields.Integer(
        compute="_compute_max_occupancy",
        store=True,
    )

    amenity_ids = fields.Many2many(
        "hotel.amenity",
        "hotel_room_category_amenity_rel",
        "room_category_id",
        "amenity_id",
        string="Amenities",
    )

    description = fields.Html()

    room_count = fields.Integer(
        compute="_compute_room_count",
    )

    # reservation_count = fields.Integer(
    #     compute="_compute_reservation_count",
    # )

    product_id = fields.Many2one(
        "product.product",
        string="Room Product",
        required=True,
        check_company=True,
        default=lambda self: self.env.ref(
            "vs_hotel_management.product_template_hotel_accommodation",
            raise_if_not_found=False,
        ),
    )

    def _compute_room_count(self):
        for record in self:
            Room = self.env["hotel.room"]
            record.room_count = Room.search_count([
                ("room_category_id", "=", record.id)
            ])

    def action_view_rooms(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Rooms",
            "res_model": "hotel.room",
            "view_mode": "list,form",
            "domain": [("room_category_id", "=", self.id)],
            "context": {
                "default_room_category_id": self.id,
            },
        }


    _sql_constraints = [
        (
            "hotel_room_category_name_company_unique",
            "unique(name, company_id)",
            "Room Category must be unique per company.",
        ),
        (
            "hotel_room_category_code_company_unique",
            "unique(code, company_id)",
            "Code must be unique per company.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "/") == "/":
                vals["code"] = self.env["ir.sequence"].next_by_code(
                    "hotel.room.category"
                ) or "/"
        return super().create(vals_list)

    def unlink(self):
        protected_product = self.env.ref(
            "vs_hotel_management.product_hotel_accommodation",
            raise_if_not_found=False,
        )

        if protected_product and protected_product in self:
            raise UserError(
                _("The Hotel Accommodation product cannot be deleted. You can archive it instead.")
            )

        return super().unlink()

    @api.depends("max_adults", "max_children")
    def _compute_max_occupancy(self):
        for rec in self:
            rec.max_occupancy = rec.max_adults + rec.max_children




