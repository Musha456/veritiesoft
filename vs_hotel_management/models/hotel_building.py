from odoo import api, fields, models


class HotelBuilding(models.Model):
    _name = "hotel.building"
    _description = "Hotel Building"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _rec_name = "display_name"
    _check_company_auto = True

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    hotel_id = fields.Many2one(
        "hotel.hotel",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )

    building_type = fields.Selection(
        [
            ("main", "Main Building"),
            ("annex", "Annex"),
            ("villa", "Villa"),
            ("bungalow", "Bungalow"),
            ("tower", "Tower"),
        ],
        default="main",
        tracking=True,
    )

    status = fields.Selection(
        [
            ("operational", "Operational"),
            ("maintenance", "Maintenance"),
            ("closed", "Closed"),
        ],
        default="operational",
        tracking=True,
    )

    capacity = fields.Integer(
        compute="_compute_capacity",
        store=True,
    )

    name = fields.Char(
        string="Building",
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

    sequence = fields.Integer(
        default=10,
    )

    image = fields.Image(
        string="Building Image",
    )

    manager_id = fields.Many2one(
        "res.users",
        string="Manager",
        tracking=True,
    )

    street = fields.Char()

    street2 = fields.Char()

    city = fields.Char()

    state_id = fields.Many2one(
        "res.country.state"
    )

    zip = fields.Char()

    country_id = fields.Many2one(
        "res.country"
    )

    latitude = fields.Float(
        digits=(10, 6),
    )

    longitude = fields.Float(
        digits=(10, 6),
    )

    active = fields.Boolean(
        default=True,
        tracking=True,
    )

    description = fields.Text()

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        # check_company=True,
    )

    floor_ids = fields.One2many(
        "hotel.building.floor",
        "building_id",
        string="Floors",
    )

    floor_count = fields.Integer(
        compute="_compute_floor_count",
        store=True,
    )
    room_count = fields.Integer(
        compute="_compute_room_count",
        store=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "/") == "/":
                vals["code"] = self.env["ir.sequence"].next_by_code(
                    "hotel.building"
                ) or "/"
        return super().create(vals_list)

    @api.depends("code", "name")
    def _compute_display_name(self):
        for record in self:
            if record.code:
                record.display_name = f"{record.code} - {record.name}"
            else:
                record.display_name = record.name

    @api.depends("floor_ids")
    def _compute_floor_count(self):
        for record in self:
            record.floor_count = len(record.floor_ids)

    @api.depends("floor_ids.room_ids")
    def _compute_room_count(self):
        Room = self.env["hotel.room"]
        for record in self:
            record.room_count = Room.search_count([
                ("building_id", "=", record.id)
            ])

    @api.depends("floor_ids.room_ids")
    def _compute_capacity(self):
        self.capacity = 100

    def action_set_operational(self):
        self.write({"status": "operational"})

    def action_set_maintenance(self):
        self.write({"status": "maintenance"})

    def action_set_closed(self):
        self.write({"status": "closed"})


    def action_view_floors(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Floors",
            "res_model": "hotel.building.floor",
            "view_mode": "list,form",
            "domain": [("building_id", "=", self.id)],
            "context": {
                "default_building_id": self.id,
            },
        }

    def action_view_rooms(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Rooms",
            "res_model": "hotel.room",
            "view_mode": "list,form",
            "domain": [("building_id", "=", self.id)],
            "context": {
                "default_building_id": self.id,
            },
        }

    _sql_constraints = [
        (
            "building_name_company_unique",
            "unique(name, company_id)",
            "Building name must be unique per company.",
        ),
        (
            "building_code_company_unique",
            "unique(code, company_id)",
            "Building code must be unique per company.",
        ),
    ]


