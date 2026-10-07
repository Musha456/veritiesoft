from odoo import api, fields, models


class HotelFloor(models.Model):
    _name = "hotel.building.floor"
    _description = "Hotel Floor"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "building_id, sequence, level"
    _rec_name = "display_name"

    name = fields.Char(
        string="Floor Name",
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

    level = fields.Integer(
        string="Floor Level",
        required=True,
        default=0,
        tracking=True,
        help="0 = Ground Floor, 1 = First Floor, -1 = Basement.",
    )

    sequence = fields.Integer(
        default=10,
    )

    building_id = fields.Many2one(
        "hotel.building",
        string="Building",
        required=True,
        ondelete="restrict",
        tracking=True,
        index=True,
    )

    company_id = fields.Many2one(
        "res.company",
        related="building_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    active = fields.Boolean(
        default=True,
        tracking=True,
    )

    description = fields.Text()

    room_ids = fields.One2many(
        "hotel.room",
        "floor_id",
        string="Rooms",
    )

    room_count = fields.Integer(
        compute="_compute_room_count",
    )

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        auto = self.env["ir.config_parameter"].sudo().get_param(
            "vs_hotel_management.auto_generate_floor_code", default=True
        )
        for vals in vals_list:
            if auto and vals.get("code", "/") in ("/", False, ""):
                vals["code"] = self.env["ir.sequence"].next_by_code(
                    "hotel.building.floor"
                ) or "/"

        return super().create(vals_list)

    @api.depends("building_id", "name")
    def _compute_display_name(self):
        for record in self:
            if record.building_id:
                record.display_name = (
                    f"{record.building_id.name} / {record.name}"
                )
            else:
                record.display_name = record.name

    @api.depends("room_ids")
    def _compute_room_count(self):
        for record in self:
            record.room_count = len(record.room_ids)

    def action_view_rooms(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Rooms",
            "res_model": "hotel.room",
            "view_mode": "list,form",
            "domain": [("floor_id", "=", self.id)],
            "context": {
                "default_floor_id": self.id,
            },
        }

    _sql_constraints = [
        (
            "floor_name_building_unique",
            "unique(name, building_id)",
            "Floor name must be unique within the building.",
        ),
        (
            "floor_level_building_unique",
            "unique(level, building_id)",
            "Floor level must be unique within the building.",
        ),
        (
            "floor_code_company_unique",
            "unique(code, company_id)",
            "Code must be unique per company.",
        ),
    ]

    