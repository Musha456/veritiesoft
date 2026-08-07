from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HotelAmenityType(models.Model):
    _name = "hotel.amenity.type"
    _description = "Hotel Amenity Type"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    name = fields.Char(
        string="Amenity Type",
        required=True,
        tracking=True,
    )

    code = fields.Char(
        string="Code",
        readonly=True,
        copy=False,
        default="/",
        index=True,
        tracking=True,
    )

    sequence = fields.Integer(
        default=10,
        tracking=True,
    )

    active = fields.Boolean(
        default=True,
        tracking=True,
    )

    description = fields.Text()

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    amenity_ids = fields.One2many(
        "hotel.amenity",
        "amenity_type_id",
        string="Amenities",
    )

    amenity_count = fields.Integer(
        compute="_compute_amenity_count",
        string="Amenities",
    )


    icon = fields.Image()


    @api.depends("amenity_ids")
    def _compute_amenity_count(self):
        for record in self:
            record.amenity_count = len(record.amenity_ids)

    @api.constrains("code")
    def _check_code(self):
        for record in self:
            if record.code and " " in record.code:
                raise ValidationError("Code cannot contain spaces.")

    _sql_constraints = [
        (
            "hotel_amenity_type_name_company_unique",
            "unique(name, company_id)",
            "Amenity Type must be unique per company.",
        ),
        (
            "hotel_amenity_type_code_company_unique",
            "unique(code, company_id)",
            "Amenity Type Code must be unique per company.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "/") == "/":
                vals["code"] = self.env["ir.sequence"].next_by_code(
                    "hotel.amenity.type"
                ) or "/"
        return super().create(vals_list)

    def action_view_amenities(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Amenities",
            "res_model": "hotel.amenity",
            "view_mode": "list,form",
            "domain": [("amenity_type_id", "=", self.id)],
            "context": {
                "default_amenity_type_id": self.id,
            },
        }

class HotelAmenity(models.Model):
    _name = "hotel.amenity"
    _description = "Hotel Amenity"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _rec_name = "name"

    name = fields.Char(
        string="Amenity",
        required=True,
        tracking=True,
    )

    code = fields.Char(
        string="Code",
        readonly=True,
        copy=False,
        default="/",
        index=True,
        tracking=True,
    )

    amenity_type_id = fields.Many2one(
        "hotel.amenity.type",
        string="Amenity Type",
        required=True,
        ondelete="restrict",
        tracking=True,
        index=True,
    )

    sequence = fields.Integer(
        default=10,
    )

    active = fields.Boolean(
        default=True,
    )

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    description = fields.Text()

    _sql_constraints = [
        (
            "hotel_amenity_name_company_unique",
            "unique(name, company_id)",
            "Amenity must be unique per company.",
        ),
        (
            "hotel_amenity_code_company_unique",
            "unique(code, company_id)",
            "Code must be unique per company.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "/") == "/":
                vals["code"] = self.env["ir.sequence"].next_by_code(
                    "hotel.amenity"
                ) or "/"
        return super().create(vals_list)

class HotelBedType(models.Model):
    _name = "hotel.bed.type"
    _description = "Hotel Bed Type"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _rec_name = "name"

    name = fields.Char(
        string="Bed Type",
        required=True,
        tracking=True,
    )

    code = fields.Char(
        string="Code",
        readonly=True,
        copy=False,
        default="/",
        index=True,
        tracking=True,
    )

    sequence = fields.Integer(
        default=10,
    )

    active = fields.Boolean(
        default=True,
    )

    image = fields.Image(
        string="Image",
        max_width=256,
        max_height=256,
    )

    description = fields.Text()

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    room_category_count = fields.Integer(
        compute="_compute_room_category_count",
        string="Room Categories",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "/") == "/":
                vals["code"] = self.env["ir.sequence"].next_by_code(
                    "hotel.bed.type"
                ) or "/"

        return super().create(vals_list)

    @api.depends()
    def _compute_room_category_count(self):
        for record in self:
            record.room_category_count = self.env[
                "hotel.room.category"
            ].search_count([
                ("bed_type_id", "=", record.id)
            ])

    def action_view_room_categories(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Rooms",
            "res_model": "hotel.room.category",
            "view_mode": "list,form",
            "domain": [("bed_type_id", "=", self.id)],
            "context": {
                "default_bed_type_id": self.id,
            },
        }

class HotelRoomStatus(models.Model):
    _name = "hotel.room.status"
    _description = "Hotel Room Status"

    name = fields.Char()

class HotelRoomImage(models.Model):
    _name = "hotel.room.image"
    _description = "Hotel Room Image"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, id"

    room_id = fields.Many2one(
        "hotel.room",
        string="Room",
        required=True,
        ondelete="cascade",
        index=True,
    )

    name = fields.Char(
        string="Title",
        required=True,
        tracking=True,
    )

    image = fields.Image(
        string="Image",
        required=True,
        max_width=1920,
        max_height=1920,
    )

    sequence = fields.Integer(
        default=10,
    )

    is_cover = fields.Boolean(
        string="Cover Image",
        tracking=True,
    )

    description = fields.Text()

    active = fields.Boolean(
        default=True,
    )

    company_id = fields.Many2one(
        related="room_id.company_id",
        store=True,
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        # Explicit cover selected
        for record in records.filtered("is_cover"):
            (record.room_id.image_ids - record).write({"is_cover": False})

        records._ensure_cover_image()
        return records

    def write(self, vals):
        res = super().write(vals)

        if "is_cover" in vals:
            for record in self.filtered("is_cover"):
                (record.room_id.image_ids - record).write({"is_cover": False})

        self._ensure_cover_image()
        return res

    def unlink(self):
        rooms = self.mapped("room_id")

        res = super().unlink()

        rooms.mapped("image_ids")._ensure_cover_image()

        return res

    def _ensure_cover_image(self):
        for room in self.mapped("room_id"):
            covers = room.image_ids.filtered("is_cover")

            if len(covers) > 1:
                keep = covers.sorted(key=lambda r: (r.sequence, r.id))[0]
                (covers - keep).write({"is_cover": False})

            elif not covers and room.image_ids:
                room.image_ids.sorted(key=lambda r: (r.sequence, r.id))[0].write({
                    "is_cover": True,
                })

    #
    # @api.constrains("is_cover", "room_id")
    # def _check_single_cover(self):
    #     for record in self.filtered("is_cover"):
    #         if self.search_count([
    #             ("room_id", "=", record.room_id.id),
    #             ("is_cover", "=", True),
    #             ("id", "!=", record.id),
    #         ]):
    #             raise ValidationError(
    #                 "Only one cover image is allowed per room."
    #             )



