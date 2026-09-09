from odoo import api, fields, models, _
from odoo.osv import expression
import pytz


class HotelHotel(models.Model):
    _name = "hotel.hotel"
    _description = "Hotel"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"
    _rec_name = "name"

    name = fields.Char(
        required=True,
        translate=True,
    )

    code = fields.Char(
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
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

    logo = fields.Image(
        string="Logo",
        max_width=512,
        max_height=512,
    )

    building_ids = fields.One2many(
        "hotel.building",
        "hotel_id",
        "Gallery Images"
    )

    service_ids = fields.One2many(
        "hotel.service",
        "hotel_id",
        "Hotel Services"
    )

    image_ids = fields.One2many(
        "hotel.hotel.image",
        "hotel_id",
        "Gallery Images"
    )

    manager_id = fields.Many2one(
        "res.users",
        string="Manager",
        tracking=True,
    )

    published = fields.Boolean(
        string="Published",
        default=True,
        tracking=True,
    )

    website_published = fields.Boolean(
        string="Website Published",
        default=True,
        tracking=True,
    )

    hero_title = fields.Char(
        translate=True,
    )

    hero_subtitle = fields.Char(
        translate=True,
    )

    meta_title = fields.Char(
        string="SEO Title",
        translate=True,
    )

    meta_description = fields.Text(
        string="SEO Description",
        translate=True,
    )

    meta_keywords = fields.Char(
        string="SEO Keywords",
        translate=True,
    )

    cover_image_id = fields.Many2one(
        "hotel.hotel.image",
        compute="_compute_cover_image",
        store=True,
    )

    hero_image = fields.Image(
        compute="_compute_hero_image",
        store=True,
    )


    booking_url = fields.Char()

    google_map_url = fields.Char()

    virtual_tour_url = fields.Char()

    # Future Relations

    # reservation_ids
    #
    # staff_ids

    phone = fields.Char()

    mobile = fields.Char()

    email = fields.Char()

    website = fields.Char()

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

    latitude = fields.Float()

    longitude = fields.Float()

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    language_id = fields.Many2one(
        "res.lang",
        string="Default Language",
        domain=[("active", "=", True)],
    )

    timezone = fields.Selection(
        selection=lambda self: [(tz, tz) for tz in pytz.all_timezones],
        string="Timezone",
        default=lambda self: self.env.user.tz,
    )

    star_rating = fields.Selection(
        [
            ("1", "★"),
            ("2", "★★"),
            ("3", "★★★"),
            ("4", "★★★★"),
            ("5", "★★★★★"),
        ],
        default="3",
    )
    # ---------------------------------------------------------
    # Reservation
    # ---------------------------------------------------------

    checkin_time = fields.Float(
        string="Check-in Time",
        default=14.0,
    )

    checkout_time = fields.Float(
        string="Check-out Time",
        default=12.0,
    )

    minimum_stay = fields.Integer(
        default=1, string="Min Stay(Day)"
    )

    maximum_stay = fields.Integer(
        default=30, string="Max Stay(Day)"
    )

    # ---------------------------------------------------------
    # Booking Rules
    # ---------------------------------------------------------

    allow_early_checkin = fields.Boolean(
        default=False,
    )

    allow_late_checkout = fields.Boolean(
        default=False,
    )

    allow_overbooking = fields.Boolean(
        default=False,
    )

    auto_assign_room = fields.Boolean(
        default=True,
    )

    allow_room_change = fields.Boolean(
        default=True,
    )

    require_guest_identification = fields.Boolean(
        default=True,
    )

    # ---------------------------------------------------------
    # Accounting
    # ---------------------------------------------------------

    tax_ids = fields.Many2many(
        "account.tax",
        string="Default Taxes",
    )

    # ---------------------------------------------------------
    # Housekeeping
    # ---------------------------------------------------------

    housekeeping_start_time = fields.Float(
        default=8.0,
    )

    housekeeping_end_time = fields.Float(
        default=18.0,
    )

    # ---------------------------------------------------------
    # Reservation
    # ---------------------------------------------------------

    reservation_expiry_hours = fields.Integer(
        default=24,
    )

    cancellation_hours = fields.Integer(
        default=24,
    )

    default_room_status = fields.Selection(
        [
            ("available", "Available"),
            ("cleaning", "Cleaning"),
            ("maintenance", "Maintenance"),
        ],
        default="available",
    )

    default_room_cleanliness = fields.Selection(
        [
            ("clean", "Clean"),
            ("dirty", "Dirty"),
        ],
        default="clean",
    )

    auto_assign_room = fields.Boolean(
        string="Assign Room Automatically",
    )

    allow_room_change = fields.Boolean(
        string="Allow Room Change",
        default=True,
    )

    # Later display these as HH:MM

    description = fields.Html(
        translate=True,
    )

    # Social Media

    facebook_url = fields.Char(
        string="Facebook",
    )

    instagram_url = fields.Char(
        string="Instagram",
    )

    linkedin_url = fields.Char(
        string="LinkedIn",
    )

    youtube_url = fields.Char(
        string="YouTube",
    )

    x_url = fields.Char(
        string="X (Twitter)",
    )

    tiktok_url = fields.Char(
        string="TikTok",
    )

    tripadvisor_url = fields.Char(
        string="TripAdvisor",
    )

    booking_com_url = fields.Char(
        string="Booking.com",
    )

    #Policies

    checkin_policy = fields.Html(
        string="Check-in Policy",
        translate=True,
    )

    checkout_policy = fields.Html(
        string="Check-out Policy",
        translate=True,
    )

    cancellation_policy = fields.Html(
        string="Cancellation Policy",
        translate=True,
    )

    child_policy = fields.Html(
        string="Children Policy",
        translate=True,
    )

    pet_policy = fields.Html(
        string="Pet Policy",
        translate=True,
    )

    smoking_policy = fields.Html(
        string="Smoking Policy",
        translate=True,
    )

    privacy_policy = fields.Html(
        string="Privacy Policy",
        translate=True,
    )

    house_rules = fields.Html(
        string="House Rules",
        translate=True,
    )

    # Statistics

    building_count = fields.Integer(
        string="Buildings",
        compute="_compute_statistics",
    )

    floor_count = fields.Integer(
        string="Floors",
        compute="_compute_statistics",
    )

    room_count = fields.Integer(
        string="Rooms",
        compute="_compute_statistics",
    )

    available_room_count = fields.Integer(
        string="Available Rooms",
        compute="_compute_statistics",
    )

    occupied_room_count = fields.Integer(
        string="Occupied Rooms",
        compute="_compute_statistics",
    )
    reserved_room_count = fields.Integer(
        string="Reserved Rooms",
        compute="_compute_statistics",
    )

    dirty_room_count = fields.Integer(
        string="Dirty Rooms",
        compute="_compute_statistics",
    )

    cleaning_room_count = fields.Integer(
        string="Cleaning Rooms",
        compute="_compute_statistics",
    )

    maintenance_room_count = fields.Integer(
        string="Maintenance Rooms",
        compute="_compute_statistics",
    )

    out_of_order_room_count = fields.Integer(
        string="Out of Order Rooms",
        compute="_compute_statistics",
    )

    guest_count = fields.Integer(
        string="Guests",
        compute="_compute_statistics",
    )

    service_count = fields.Integer(
        string="Services",
        compute="_compute_statistics",
    )

    gallery_count = fields.Integer(
        string="Gallery",
        compute="_compute_statistics",
    )

    reservation_count = fields.Integer(
        string="Reservations",
        compute="_compute_statistics",
    )

    @api.depends("image_ids", "image_ids.is_cover")
    def _compute_cover_image(self):
        for hotel in self:
            hotel.cover_image_id = hotel.image_ids.filtered(
                "is_cover"
            )[:1]

    @api.depends("cover_image_id", "cover_image_id.image")
    def _compute_hero_image(self):
        for hotel in self:
            hotel.hero_image = hotel.cover_image_id.image


    @api.depends(
        "building_ids",
        "building_ids.floor_ids",
        "building_ids.floor_ids.room_ids",
        "service_ids",
        "image_ids",
    )
    def _compute_statistics(self):
        for hotel in self:
            buildings = hotel.building_ids
            floors = buildings.mapped("floor_ids")
            rooms = floors.mapped("room_ids")

            hotel.building_count = len(buildings)
            hotel.floor_count = len(floors)
            hotel.room_count = len(rooms)

            hotel.available_room_count = len(
                rooms.filtered(lambda r: r.status == "available")
            )

            hotel.occupied_room_count = len(
                rooms.filtered(lambda r: r.status == "occupied")
            )

            hotel.reserved_room_count = len(
                rooms.filtered(lambda r: r.status == "reserved")
            )

            hotel.dirty_room_count = len(
                rooms.filtered(lambda r: r.status == "dirty")
            )

            hotel.cleaning_room_count = len(
                rooms.filtered(lambda r: r.status == "cleaning")
            )

            hotel.maintenance_room_count = len(
                rooms.filtered(lambda r: r.status == "maintenance")
            )

            hotel.out_of_order_room_count = len(
                rooms.filtered(lambda r: r.status == "out_of_order")
            )

            hotel.service_count = len(hotel.service_ids)
            hotel.gallery_count = len(hotel.image_ids)

            # Will be implemented when reservation module is added
            hotel.reservation_count = 0
            hotel.guest_count = 0

    #
    # reservation_count

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "/") == "/":
                vals["code"] = self.env["ir.sequence"].next_by_code(
                    "hotel.hotel"
                ) or "/"
        return super().create(vals_list)

    # @api.model
    # def _name_search(self, name='', args=None, operator='ilike', limit=100, order=None):
    #     args = args or []
    #     domain = []
    #
    #     if name:
    #         domain = ['|', '|',
    #                   ('name', operator, name),
    #                   ('code', operator, name),
    #                   ('description', operator, name),
    #                   ]
    #
    #     return self._search(expression.AND([domain, args]), limit=limit, order=order)

    def action_view_buildings(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Buildings",
            "res_model": "hotel.building",
            "view_mode": "list,form",
            "domain": [("hotel_id", "=", self.id)],
            "context": {
                "default_hotel_id": self.id,
            },
        }

    def action_view_floors(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Floors",
            "res_model": "hotel.building.floor",
            "view_mode": "list,form",
            "domain": [("building_id.hotel_id", "=", self.id)],
        }

    def action_view_rooms(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Rooms",
            "res_model": "hotel.room",
            "view_mode": "list,form",
            "domain": [("building_id.hotel_id", "=", self.id)],
        }

    def action_view_services(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Services",
            "res_model": "hotel.service",
            "view_mode": "list,form",
            "domain": [("hotel_id", "=", self.id)],
        }

    def action_view_gallery(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Gallery",
            "res_model": "hotel.hotel.image",
            "view_mode": "kanban,list,form",
            "domain": [("hotel_id", "=", self.id)],
        }

    # def action_view_reservations(self):
    #     self.ensure_one()
    #
    #     return {
    #         "type": "ir.actions.act_window",
    #         "name": "Reservations",
    #         "res_model": "hotel.reservation",
    #         "view_mode": "list,form",
    #         "domain": [("hotel_id", "=", self.id)],
    #     }

    _sql_constraints = [
        (
            "hotel_code_company_unique",
            "unique(code, company_id)",
            "Hotel code must be unique per company.",
        ),
    ]
