from odoo import api, fields, models
from odoo.exceptions import ValidationError
from collections import defaultdict
from markupsafe import Markup, escape


class HotelRoom(models.Model):
    _name = "hotel.room"
    _description = "Hotel Room"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, room_number"
    _rec_name = "display_name"

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    room_number = fields.Char(
        required=True,
        tracking=True,
    )

    code = fields.Char(
        readonly=True,
        default="/",
        copy=False,
        index=True,
    )

    sequence = fields.Integer(default=10)

    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    building_id = fields.Many2one(
        "hotel.building",
        required=True,
        ondelete="restrict",
    )

    floor_id = fields.Many2one(
        "hotel.building.floor",
        required=True,
        ondelete="restrict",
    )

    room_category_id = fields.Many2one(
        "hotel.room.category",
        required=True,
        ondelete="restrict",
        tracking=True,
    )

    bed_type_id = fields.Many2one(related='room_category_id.bed_type_id')
    bed_count = fields.Integer(related='room_category_id.bed_count')
    room_size = fields.Float(related='room_category_id.room_size')
    room_size_uom = fields.Selection(related='room_category_id.room_size_uom')
    amenity_ids = fields.Many2many(related="room_category_id.amenity_ids")

    amenity_type_ids = fields.Many2many(
        "hotel.amenity.type",
        compute="_compute_amenity_type_ids",
        store=True,
        string="Amenity Types",
    )

    amenity_groups_html = fields.Html(
        compute="_compute_amenity_groups_html",
        sanitize=False,
    )

    image_ids = fields.One2many(
        "hotel.room.image",
        "room_id",
        string="Images",
    )

    cover_image_id = fields.Many2one(
        "hotel.room.image",
        string="Cover Image",
        compute="_compute_cover_image_id",
        store=True,
        readonly=True,
    )

    cover_image = fields.Image(
        compute="_compute_cover_image",
        store=True,
    )

    # To be use seperate model for better statuses customization
    status = fields.Selection(
        [
            ("available", "Available"),
            ("reserved", "Reserved"),
            ("occupied", "Occupied"),
            ("dirty", "Dirty"),
            ("cleaning", "Cleaning"),
            ("maintenance", "Maintenance"),
            ("out_of_order", "Out of Order"),
        ],
        default="available",
        tracking=True,
    )

    description = fields.Html(
        string="Description",
        translate=True,
        sanitize=True,
    )

    reservation_count = fields.Integer(
        compute="_compute_reservation_count",
    )

    housekeeping_count = fields.Integer(
        compute="_compute_housekeeping_count",
    )

    maintenance_count = fields.Integer(
        compute="_compute_maintenance_count",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "/") == "/":
                vals["code"] = self.env["ir.sequence"].next_by_code(
                    "hotel.room"
                ) or "/"
        return super().create(vals_list)

    @api.depends("room_number", "room_category_id")
    def _compute_display_name(self):
        for room in self:
            if room.room_category_id:
                room.display_name = (
                    f"{room.room_number} - {room.room_category_id.name}"
                )
            else:
                room.display_name = room.room_number

    @api.depends("image_ids", "image_ids.is_cover", "image_ids.image")
    def _compute_cover_image_id(self):
        for room in self:
            room.cover_image_id = room.image_ids.filtered("is_cover")[:1]


    @api.depends("cover_image_id", "cover_image_id.image")
    def _compute_cover_image(self):
        for hotel in self:
            hotel.cover_image = hotel.cover_image_id.image


    @api.depends("room_category_id.amenity_ids.amenity_type_id")
    def _compute_amenity_type_ids(self):
        for room in self:
            room.amenity_type_ids = room.amenity_ids.mapped("amenity_type_id")

    @api.depends(
        "room_category_id",
        "room_category_id.amenity_ids",
        "room_category_id.amenity_ids.amenity_type_id",
        "room_category_id.amenity_ids.amenity_type_id.icon",
        "room_category_id.amenity_ids.amenity_type_id.name",
    )
    @api.depends(
        "room_category_id.amenity_ids",
        "room_category_id.amenity_ids.name",
        "room_category_id.amenity_ids.amenity_type_id",
        "room_category_id.amenity_ids.amenity_type_id.name",
        "room_category_id.amenity_ids.amenity_type_id.icon",
    )
    def _compute_amenity_groups_html(self):
        for room in self:

            groups = defaultdict(list)

            for amenity in room.room_category_id.amenity_ids:
                groups[amenity.amenity_type_id].append(amenity)

            html = '<div class="hotel_room_amenity_groups">'

            for amenity_type, amenities in groups.items():

                html += f"""
                <div class="hotel_room_amenity_group">

                    <div class="hotel_room_amenity_group_header">

                        <img
                            src="/web/image/hotel.amenity.type/{amenity_type.id}/icon"
                            class="hotel_room_amenity_type_icon"/>

                        <span class="hotel_room_amenity_type_name">
                            {escape(amenity_type.name)}
                        </span>

                    </div>

                    <div class="hotel_room_amenity_list">
                """

                for amenity in amenities:
                    html += f"""
                        <div class="hotel_room_amenity_item">
                            {escape(amenity.name)}
                        </div>
                    """

                html += """
                    </div>
                </div>
                """

            html += "</div>"

            room.amenity_groups_html = Markup(html)

    @api.onchange("building_id")
    def _onchange_building_id(self):
        self.floor_id = False

    def action_mark_reserved(self):
        self.write({"status": "reserved"})

    def action_check_in(self):
        self.write({"status": "occupied"})

    def action_mark_dirty(self):
        self.write({"status": "dirty"})

    def action_start_cleaning(self):
        self.write({"status": "cleaning"})

    def action_mark_available(self):
        self.write({"status": "available"})

    def action_start_maintenance(self):
        self.write({"status": "maintenance"})

    def action_mark_out_of_order(self):
        self.write({"status": "out_of_order"})

    def action_finish_maintenance(self):
        self.write({"status": "available"})

    _sql_constraints = [
        (
            "room_number_company_unique",
            "unique(room_number, company_id)",
            "Room number must be unique per company.",
        ),
        (
            "room_code_company_unique",
            "unique(code, company_id)",
            "Code must be unique per company.",
        ),
    ]
