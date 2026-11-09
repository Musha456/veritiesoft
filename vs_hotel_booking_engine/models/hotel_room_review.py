# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HotelRoomReview(models.Model):
    _name = "hotel.room.review"
    _description = "Hotel Room & Category Guest Review"
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Title",
        required=True,
    )

    room_category_id = fields.Many2one(
        "hotel.room.category",
        string="Room Category",
        required=True,
        ondelete="cascade",
        index=True,
    )

    room_id = fields.Many2one(
        "hotel.room",
        string="Specific Room",
        ondelete="set null",
        index=True,
    )

    hotel_id = fields.Many2one(
        "hotel.hotel",
        string="Hotel",
        compute="_compute_hotel_id",
        store=True,
        readonly=False,
        index=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        compute="_compute_company_id",
        store=True,
        readonly=False,
        index=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Guest Partner",
        ondelete="set null",
        index=True,
    )

    guest_name = fields.Char(
        string="Guest Name",
        required=True,
    )

    guest_email = fields.Char(
        string="Guest Email",
    )

    rating = fields.Integer(
        string="Rating",
        required=True,
        default=5,
    )

    comment = fields.Text(
        string="Review Comment",
        required=True,
    )

    review_date = fields.Date(
        string="Review Date",
        default=fields.Date.context_today,
        required=True,
    )

    is_published = fields.Boolean(
        string="Published on Website",
        default=True,
    )

    stay_date = fields.Char(
        string="Stay Period",
        help="Optional reference to the stay period (e.g. October 2026)",
    )

    @api.depends("room_id", "room_id.hotel_id")
    def _compute_hotel_id(self):
        for rec in self:
            if rec.room_id and rec.room_id.hotel_id:
                rec.hotel_id = rec.room_id.hotel_id
            elif not rec.hotel_id:
                rec.hotel_id = False

    @api.depends("hotel_id", "hotel_id.company_id", "room_category_id", "room_category_id.company_id")
    def _compute_company_id(self):
        for rec in self:
            if rec.hotel_id and rec.hotel_id.company_id:
                rec.company_id = rec.hotel_id.company_id
            elif rec.room_category_id and rec.room_category_id.company_id:
                rec.company_id = rec.room_category_id.company_id
            else:
                rec.company_id = self.env.company

    @api.constrains("rating")
    def _check_rating(self):
        for rec in self:
            if rec.rating < 1 or rec.rating > 5:
                raise ValidationError(_("Rating must be between 1 and 5 stars."))


class HotelRoomCategory(models.Model):
    _inherit = "hotel.room.category"

    review_ids = fields.One2many(
        "hotel.room.review",
        "room_category_id",
        string="Guest Reviews",
    )

    rating_avg = fields.Float(
        string="Average Rating",
        compute="_compute_rating_stats",
        store=True,
        digits=(3, 1),
    )

    review_count = fields.Integer(
        string="Reviews Count",
        compute="_compute_rating_stats",
        store=True,
    )

    @api.depends("review_ids.rating", "review_ids.is_published")
    def _compute_rating_stats(self):
        for cat in self:
            published_reviews = cat.review_ids.filtered(lambda r: r.is_published)
            cat.review_count = len(published_reviews)
            if cat.review_count:
                cat.rating_avg = round(sum(published_reviews.mapped("rating")) / cat.review_count, 1)
            else:
                cat.rating_avg = 5.0  # Default 5-star baseline


class HotelRoom(models.Model):
    _inherit = "hotel.room"

    review_ids = fields.One2many(
        "hotel.room.review",
        "room_id",
        string="Room Reviews",
    )

    rating_avg = fields.Float(
        string="Average Rating",
        compute="_compute_room_rating_stats",
        store=True,
        digits=(3, 1),
    )

    review_count = fields.Integer(
        string="Reviews Count",
        compute="_compute_room_rating_stats",
        store=True,
    )

    @api.depends("review_ids.rating", "review_ids.is_published")
    def _compute_room_rating_stats(self):
        for room in self:
            published_reviews = room.review_ids.filtered(lambda r: r.is_published)
            room.review_count = len(published_reviews)
            if room.review_count:
                room.rating_avg = round(sum(published_reviews.mapped("rating")) / room.review_count, 1)
            else:
                room.rating_avg = room.room_category_id.rating_avg or 5.0
