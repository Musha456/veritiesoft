# -*- coding: utf-8 -*-
import logging
from datetime import datetime, date, timedelta
from odoo import http, fields, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class HotelBookingEngineController(http.Controller):

    @property
    def env(self):
        return self._get_env()

    def _get_env(self):
        try:
            return request.env
        except (RuntimeError, Exception):
            return getattr(self, "_test_env", None)

    @http.route(["/hotel", "/hotel/book", "/hotel/booking"], type="http", auth="public", website=True, sitemap=True)
    def hotel_booking_page(self, hotel_id=None, **kwargs):
        """
        Main Online Booking Engine & Homepage Banner:
        Displays an advanced hero banner with dynamic hotel imagery, title & subtitle,
        floating availability search card, multi-currency switcher, and 4-step booking workflow.
        """
        env = self._get_env()
        Hotel = env["hotel.hotel"].sudo()
        hotels = Hotel.search([])
        if not hotels:
            return request.render("vs_hotel_booking_engine.no_hotels_available", {})

        selected_hotel = Hotel.browse(int(hotel_id)) if hotel_id else hotels[0]
        if not selected_hotel.exists():
            selected_hotel = hotels[0]

        # Dates default: tomorrow to +2 days
        today = date.today()
        default_ci = kwargs.get("check_in") or (today + timedelta(days=1)).strftime("%Y-%m-%d")
        default_co = kwargs.get("check_out") or (today + timedelta(days=3)).strftime("%Y-%m-%d")

        company = selected_hotel.company_id or env.company
        policy = getattr(company, "advance_booking_payment_policy", "optional")
        percentage = getattr(company, "advance_booking_percentage", 30.0)

        # Active currencies for dynamic currency switcher
        currencies = env["res.currency"].sudo().search([("active", "=", True)], order="id asc")
        current_currency = selected_hotel.currency_id or env.company.currency_id

        # Pre-fill logged-in user data
        partner = env.user.partner_id if not env.user._is_public() else False

        countries = env["res.country"].sudo().search([])

        # Hero Image URL
        hero_img_url = f"/web/image/hotel.hotel/{selected_hotel.id}/hero_image" if selected_hotel.hero_image else (
            f"/web/image/hotel.hotel/{selected_hotel.id}/cover_image" if selected_hotel.cover_image else ""
        )

        values = {
            "hotels": hotels,
            "hotel": selected_hotel,
            "hero_title": selected_hotel.hero_title or _("Experience Luxury & Authentic Comfort"),
            "hero_subtitle": selected_hotel.hero_subtitle or _("Book your stay directly for exclusive best-rate guarantees, personalized service, and flexible check-in."),
            "hero_img_url": hero_img_url,
            "currencies": currencies,
            "current_currency": current_currency,
            "default_check_in": default_ci,
            "default_check_out": default_co,
            "default_adults": int(kwargs.get("adults", 2)),
            "default_children": int(kwargs.get("children", 0)),
            "policy": policy,
            "advance_percentage": percentage,
            "partner": partner,
            "countries": countries,
            "theme_style": selected_hotel.theme_style,
        }
        return request.render("vs_hotel_booking_engine.booking_page", values)

    @http.route("/hotel/booking/api/availability", type="jsonrpc", auth="public", methods=["POST"])
    def check_availability_api(self, hotel_id, check_in, check_out, adults=1, children=0, currency_id=None):
        """
        JSON-RPC Endpoint: Queries available room categories and operational rooms
        for a selected hotel and date range with transparent pricing, multi-currency conversion,
        and add-on services.
        """
        env = self._get_env()
        Hotel = env["hotel.hotel"].sudo()
        hotel = Hotel.browse(int(hotel_id))
        if not hotel.exists():
            return {"error": _("Selected hotel does not exist.")}

        try:
            ci_date = datetime.strptime(check_in, "%Y-%m-%d")
            co_date = datetime.strptime(check_out, "%Y-%m-%d")
        except Exception:
            return {"error": _("Invalid check-in or check-out date format.")}

        if co_date <= ci_date:
            return {"error": _("Check-out date must be after check-in date.")}

        nights = max(1, (co_date.date() - ci_date.date()).days)

        # Standard check-in / check-out times from hotel
        ci_hour = int(hotel.check_in_time) if hasattr(hotel, "check_in_time") else 14
        co_hour = int(hotel.check_out_time) if hasattr(hotel, "check_out_time") else 11
        ci_dt = ci_date.replace(hour=ci_hour, minute=0, second=0)
        co_dt = co_date.replace(hour=co_hour, minute=0, second=0)

        # Target Currency for multi-currency conversion
        target_currency = hotel.currency_id
        if currency_id:
            req_curr = env["res.currency"].sudo().browse(int(currency_id))
            if req_curr.exists():
                target_currency = req_curr

        def convert_price(amount):
            if target_currency.id == hotel.currency_id.id:
                return round(amount, 2)
            converted = hotel.currency_id._convert(
                amount, target_currency, hotel.company_id or env.company, fields.Date.today()
            )
            return round(converted, 2)

        req_adults = int(adults or 1)
        req_children = int(children or 0)
        req_total_guests = req_adults + req_children

        # Operational rooms in this hotel
        Room = env["hotel.room"].sudo()
        rooms = Room.search([
            ("hotel_id", "=", hotel.id),
            ("building_id.status", "in", ("operational", False)),
            ("status", "in", ("available", "reserved")),
        ])

        categories = {}
        for room in rooms:
            if not room.is_available(check_in=ci_dt, check_out=co_dt, raise_exception=False):
                continue

            cat = room.room_category_id
            if not cat:
                continue

            # Proper Occupancy & Guest Capacity Filtering
            cat_max_occ = cat.max_occupancy or (cat.max_adults + cat.max_children)
            if cat.max_adults and req_adults > cat.max_adults:
                continue
            if cat_max_occ and req_total_guests > cat_max_occ:
                continue
            if req_children > 0 and hasattr(cat, "max_children") and req_children > cat.max_children:
                continue

            if cat.id not in categories:
                # Get default rate plan
                rate_plan = env["hotel.rate.plan"].sudo().search([
                    ("hotel_id", "=", hotel.id),
                    ("room_category_ids", "in", [cat.id]),
                    ("state", "=", "active"),
                ], limit=1, order="id asc")
                base_nightly = (
                    rate_plan.base_price if (rate_plan and rate_plan.base_price)
                    else (cat.product_id.list_price if (cat.product_id and cat.product_id.list_price) else 100.0)
                )
                converted_nightly = convert_price(base_nightly)

                amenities = []
                for a in cat.amenity_ids[:6]:
                    amenities.append({
                        "name": a.name,
                        "type": a.amenity_type_id.name if a.amenity_type_id else "",
                    })

                # Category image resolution:
                # 1. Direct category image
                # 2. Cover image of any room in this category
                # 3. First room image of any room in this category
                # 4. Fallback luxury image
                img_url = ""
                if cat.image:
                    img_url = f"/web/image/hotel.room.category/{cat.id}/image"
                else:
                    for r in rooms.filtered(lambda rm: rm.room_category_id.id == cat.id):
                        if r.cover_image:
                            img_url = f"/web/image/hotel.room/{r.id}/cover_image"
                            break
                        elif r.image_ids:
                            img_url = f"/web/image/hotel.room.image/{r.image_ids[0].id}/image"
                            break
                if not img_url:
                    img_url = "/vs_hotel_booking_engine/static/src/img/luxury_hero.jpg"

                categories[cat.id] = {
                    "id": cat.id,
                    "name": cat.name,
                    "code": cat.code or "",
                    "description": cat.description or "",
                    "max_adults": cat.max_adults or 2,
                    "max_children": cat.max_children or 0,
                    "max_occupancy": cat_max_occ,
                    "room_size": cat.room_size or "",
                    "bed_type": cat.bed_type_id.name if cat.bed_type_id else "",
                    "bed_type_icon": f"/web/image/hotel.bed.type/{cat.bed_type_id.id}/icon" if cat.bed_type_id and cat.bed_type_id.icon else "",
                    "nightly_price": converted_nightly,
                    "raw_price": base_nightly,
                    "rate_plan_id": rate_plan.id if rate_plan else False,
                    "rate_plan_name": rate_plan.name if rate_plan else _("Standard Rate"),
                    "cancellation_policy": rate_plan.cancellation_policy if rate_plan else "flexible",
                    "amenities": amenities,
                    "image_url": img_url,
                    "rating_avg": getattr(cat, "rating_avg", 5.0) or 5.0,
                    "review_count": getattr(cat, "review_count", 0) or 0,
                    "available_rooms": [],
                }

            # Room image thumbnail
            room_img = f"/web/image/hotel.room/{room.id}/cover_image" if hasattr(room, "cover_image") and room.cover_image else (
                f"/web/image/hotel.room.image/{room.image_ids[0].id}/image" if hasattr(room, "image_ids") and room.image_ids else categories[cat.id]["image_url"]
            )

            categories[cat.id]["available_rooms"].append({
                "id": room.id,
                "room_number": room.room_number,
                "name": room.display_name,
                "floor": room.floor_id.name if room.floor_id else "",
                "building": room.building_id.name if room.building_id else "",
                "image_url": room_img,
            })

        # Fetch Add-on Services (is_hotel_service=True)
        ServiceProduct = env["product.product"].sudo()
        services_records = ServiceProduct.search([
            ("is_hotel_service", "=", True),
            ("sale_ok", "=", True),
            "|", ("hotel_id", "=", False), ("hotel_id", "=", hotel.id),
        ])
        services_list = []
        for s in services_records:
            conv_s_price = convert_price(s.list_price)
            services_list.append({
                "id": s.id,
                "name": s.name,
                "price": conv_s_price,
                "description": s.hotel_description or s.description_sale or "",
                "is_complimentary": getattr(s, "is_complimentary", False),
                "image_url": f"/web/image/product.product/{s.id}/image_128" if s.image_128 else "",
            })

        company = hotel.company_id or env.company
        policy = getattr(company, "advance_booking_payment_policy", "optional")
        percentage = getattr(company, "advance_booking_percentage", 30.0)

        return {
            "success": True,
            "hotel": {
                "id": hotel.id,
                "name": hotel.name,
                "primary_color": hotel.primary_color or "#1e3a8a",
                "secondary_color": hotel.secondary_color or "#2563eb",
                "accent_color": hotel.accent_color or "#f59e0b",
            },
            "currency": {
                "id": target_currency.id,
                "name": target_currency.name,
                "symbol": target_currency.symbol or "$",
                "rate": target_currency.rate,
            },
            "nights": nights,
            "policy": policy,
            "advance_percentage": percentage,
            "categories": list(categories.values()),
            "services": services_list,
        }

    @http.route(["/hotel/room_type/<int:category_id>", "/hotel/room/<int:room_id>"], type="http", auth="public", website=True)
    def room_details_page(self, category_id=None, room_id=None, **kwargs):
        """
        Dedicated Room Details & Showcase Page (Opens in New Tab):
        Features high-resolution carousel image gallery, room technical specifications,
        bed icons, amenities breakdown, verified guest reviews, star ratings, and review submission.
        """
        env = self._get_env()
        RoomCat = env["hotel.room.category"].sudo()
        Room = env["hotel.room"].sudo()

        room = False
        if room_id:
            room = Room.browse(room_id)
            category = room.room_category_id
        else:
            category = RoomCat.browse(category_id)

        if not category or not category.exists():
            return request.redirect("/hotel")

        hotel = category.hotel_id

        # Images list for carousel gallery
        images = []
        if room and hasattr(room, "image_ids") and room.image_ids:
            for img in room.image_ids:
                images.append({
                    "id": img.id,
                    "url": f"/web/image/hotel.room.image/{img.id}/image",
                    "caption": img.name or room.display_name,
                })
        elif category.image:
            images.append({
                "id": 0,
                "url": f"/web/image/hotel.room.category/{category.id}/image",
                "caption": category.name,
            })

        # Fetch reviews for this category / room
        Review = env["hotel.room.review"].sudo()
        domain = [("room_category_id", "=", category.id), ("is_published", "=", True)]
        reviews = Review.search(domain, order="create_date desc")

        values = {
            "hotel": hotel,
            "category": category,
            "room": room,
            "images": images,
            "reviews": reviews,
            "rating_avg": category.rating_avg or 5.0,
            "review_count": len(reviews),
            "theme_style": hotel.theme_style,
        }
        return request.render("vs_hotel_booking_engine.room_detail_showcase_page", values)

    @http.route("/hotel/review/submit", type="jsonrpc", auth="public", methods=["POST"])
    def submit_review_api(self, category_id, guest_name, rating, comment, title="Guest Experience", room_id=None, guest_email=None):
        """Allows guests to submit reviews for room categories/rooms."""
        env = self._get_env()
        Review = env["hotel.room.review"].sudo()

        try:
            rating_val = int(rating)
            if rating_val < 1 or rating_val > 5:
                rating_val = 5
        except Exception:
            rating_val = 5

        partner_id = env.user.partner_id.id if env.user and not env.user._is_public() else False

        review = Review.create({
            "room_category_id": int(category_id),
            "room_id": int(room_id) if room_id else False,
            "partner_id": partner_id,
            "guest_name": (guest_name or "Guest").strip(),
            "guest_email": (guest_email or "").strip(),
            "rating": rating_val,
            "name": (title or "Guest Stay Review").strip(),
            "comment": comment.strip(),
            "review_date": fields.Date.context_today(Review),
            "is_published": True,
        })
        return {
            "success": True,
            "review_id": review.id,
            "message": _("Thank you! Your review has been submitted successfully."),
        }

    @http.route("/hotel/booking/submit", type="jsonrpc", auth="public", methods=["POST"])
    def submit_booking_api(self, **payload):
        """
        JSON Endpoint: Validates and creates the reservation with multi-room booking,
        primary guest matching, accompanying guests, add-on services, and creates the
        record in DRAFT state. Queues both guest thank-you and management notification emails.
        """
        env = self._get_env()
        hotel_id = payload.get("hotel_id")
        check_in = payload.get("check_in")
        check_out = payload.get("check_out")
        rooms_selected = payload.get("rooms", [])

        if not hotel_id or not check_in or not check_out or not rooms_selected:
            return {"error": _("Incomplete booking information. Please select dates and rooms.")}

        Hotel = env["hotel.hotel"].sudo()
        hotel = Hotel.browse(int(hotel_id))
        if not hotel.exists():
            return {"error": _("Selected hotel does not exist.")}

        try:
            ci_date = datetime.strptime(check_in, "%Y-%m-%d")
            co_date = datetime.strptime(check_out, "%Y-%m-%d")
        except Exception:
            return {"error": _("Invalid date format.")}

        ci_hour = int(hotel.check_in_time) if hasattr(hotel, "check_in_time") else 14
        co_hour = int(hotel.check_out_time) if hasattr(hotel, "check_out_time") else 11
        ci_dt = ci_date.replace(hour=ci_hour, minute=0, second=0)
        co_dt = co_date.replace(hour=co_hour, minute=0, second=0)

        # 1. Partner matching / creation
        guest_email = (payload.get("guest_email") or "").strip()
        guest_phone = (payload.get("guest_phone") or "").strip()
        guest_name = (payload.get("guest_name") or "Online Guest").strip()
        country_id = payload.get("guest_country_id")

        raw_id_type = payload.get("guest_id_type", "national_id")
        id_type = "national_id" if raw_id_type == "cnic" else raw_id_type
        if id_type not in ("passport", "national_id", "driving_license", "other"):
            id_type = "national_id"

        Partner = env["res.partner"].sudo()
        partner = False
        if env.user and not env.user._is_public():
            partner = env.user.partner_id

        if not partner and guest_email:
            partner = Partner.search([("email", "=ilike", guest_email)], limit=1)
        if not partner and guest_phone:
            partner = Partner.search([("phone", "=", guest_phone)], limit=1)

        partner_vals = {
            "name": guest_name,
            "email": guest_email,
            "phone": guest_phone,
            "is_hotel_guest": True,
            "id_type": id_type,
            "id_number": payload.get("guest_id_number", ""),
            "street": payload.get("guest_street", ""),
            "city": payload.get("guest_city", ""),
        }
        if country_id:
            try:
                partner_vals["country_id"] = int(country_id)
            except Exception:
                pass

        if not partner:
            partner = Partner.create(partner_vals)
        else:
            partner.write(partner_vals)

        # 2. Build reservation lines & validate availability
        Room = env["hotel.room"].sudo()
        RatePlan = env["hotel.rate.plan"].sudo()
        line_vals = []
        total_room_cost = 0.0

        for item in rooms_selected:
            room_id = int(item.get("room_id"))
            room = Room.browse(room_id)
            if not room.exists():
                return {"error": _("Selected room does not exist.")}

            # Check availability
            if not room.is_available(check_in=ci_dt, check_out=co_dt, raise_exception=False):
                return {"error": _("Room %s is no longer available. Please select another room.") % room.display_name}

            rate_plan_id = item.get("rate_plan_id")
            rate_plan = RatePlan.browse(int(rate_plan_id)) if rate_plan_id else False
            if not rate_plan or not rate_plan.exists():
                rate_plan = RatePlan.search([
                    ("hotel_id", "=", hotel.id),
                    ("room_category_ids", "in", [room.room_category_id.id]),
                    ("state", "=", "active"),
                ], limit=1)

            room_price = rate_plan.base_price if rate_plan else 0.0
            nights = max(1, (co_dt.date() - ci_dt.date()).days)
            total_room_cost += (room_price * nights)

            line_vals.append((0, 0, {
                "room_id": room.id,
                "room_category_id": room.room_category_id.id,
                "rate_plan_id": rate_plan.id if rate_plan else False,
                "building_id": room.building_id.id if room.building_id else False,
                "floor_id": room.floor_id.id if room.floor_id else False,
                "adults": int(item.get("adults", payload.get("adults", 1))),
                "children": int(item.get("children", payload.get("children", 0))),
                "check_in": ci_dt,
                "check_out": co_dt,
                "room_price": room_price,
            }))

        # 3. Accompanying guests
        accompanying_vals = []
        for ag in payload.get("accompanying_guests", []):
            if ag.get("name"):
                accompanying_vals.append((0, 0, {
                    "name": ag["name"],
                    "id_type": ag.get("id_type", "national_id"),
                    "id_number": ag.get("id_number", ""),
                    "age_category": ag.get("age_category", "adult"),
                    "phone": ag.get("phone", ""),
                }))

        # 4. Add-on Services Selection
        selected_service_ids = payload.get("services", [])
        ServiceProduct = env["product.product"].sudo()
        total_service_cost = 0.0
        service_products = []
        if selected_service_ids:
            service_products = ServiceProduct.browse([int(sid) for sid in selected_service_ids if str(sid).isdigit()])
            total_service_cost = sum(sp.list_price for sp in service_products)

        # 5. Advance payment calculations
        grand_total_estimated = total_room_cost + total_service_cost
        company = hotel.company_id or env.company
        advance_percentage = getattr(company, "advance_booking_percentage", 30.0) or 30.0
        advance_required = round(grand_total_estimated * (advance_percentage / 100.0), 2)

        payment_choice = payload.get("advance_payment_choice") or payload.get("payment_choice", "pay_at_hotel")
        if payment_choice in ("pay_later", "later", "hotel"):
            payment_choice = "pay_at_hotel"
        advance_paid = 0.0
        advance_status = "pay_at_hotel"

        if payment_choice == "advance":
            advance_paid = advance_required
            advance_status = "paid"
        elif payment_choice == "full":
            advance_paid = grand_total_estimated
            advance_status = "paid"

        # 6. Create Hotel Reservation in DRAFT state
        Reservation = env["hotel.reservation"].sudo()
        res_vals = {
            "hotel_id": hotel.id,
            "partner_id": partner.id,
            "check_in": ci_dt,
            "check_out": co_dt,
            "booking_source": "website",
            "is_online_booking": True,
            "special_request": payload.get("special_requests") or payload.get("notes", ""),
            "guest_notes": payload.get("special_requests") or payload.get("notes", ""),
            "line_ids": line_vals,
            "accompanying_guest_ids": accompanying_vals,
            "advance_payment_choice": payment_choice,
            "advance_payment_amount": advance_required,
            "advance_paid_amount": advance_paid,
            "advance_payment_status": advance_status,
        }

        reservation = Reservation.create(res_vals)

        # Attach add-on service lines to the first reservation room line
        if service_products and reservation.line_ids:
            target_line = reservation.line_ids[0]
            ServiceLine = env["hotel.reservation.service.line"].sudo()
            for sp in service_products:
                ServiceLine.create({
                    "reservation_line_id": target_line.id,
                    "product_id": sp.id,
                    "quantity": 1.0,
                    "price_unit": sp.list_price,
                    "serve_date": ci_dt,
                })

        # Generate folio in draft with room & service charges
        try:
            Folio = env["hotel.guest.folio"].sudo()
            folio = Folio.create({
                "reservation_id": reservation.id,
                "partner_id": partner.id,
                "hotel_id": hotel.id,
                "company_id": hotel.company_id.id if hotel.company_id else env.company.id,
            })
            # Room charges
            for l in reservation.line_ids:
                folio.add_charge(
                    description=_("Accommodation: Room %s (%s nights)") % (l.room_id.room_number, l.night_count),
                    charge_type="room",
                    unit_price=l.room_price,
                    quantity=l.night_count,
                    reservation_line=l,
                )
            # Service charges
            for sp in service_products:
                folio.add_charge(
                    description=_("Service: %s") % sp.name,
                    charge_type="service",
                    product=sp,
                    unit_price=sp.list_price,
                    quantity=1.0,
                )
            # Advance payment credit if paid online
            if advance_paid > 0:
                folio.add_charge(
                    description=_("Advance Booking Online Deposit"),
                    charge_type="payment",
                    unit_price=-advance_paid,
                    quantity=1.0,
                    source_document=f"WEB/{reservation.name}",
                )
        except Exception as e:
            _logger.warning("Folio auto-generation notice for %s: %s", reservation.name, e)

        # 7. Asynchronously Queue Emails (Guest Thank-You & Management Alert)
        reservation.send_online_booking_queued_emails()

        return {
            "success": True,
            "reservation_id": reservation.id,
            "reservation_name": reservation.name,
            "redirect_url": f"/hotel/booking/confirmation/{reservation.id}",
        }

    @http.route("/hotel/booking/confirmation/<int:res_id>", type="http", auth="public", website=True)
    def booking_confirmation_page(self, res_id, **kwargs):
        """
        Booking Confirmation & Voucher Display Page:
        Confirms receipt of the booking request, displays itemized pricing, stay summary,
        stay instructions, and direct links to Guest Portal & PDF Voucher.
        """
        Reservation = request.env["hotel.reservation"].sudo()
        reservation = Reservation.browse(res_id)
        if not reservation.exists():
            return request.redirect("/hotel")

        hotel = reservation.hotel_id
        values = {
            "reservation": reservation,
            "hotel": hotel,
            "theme_style": hotel.theme_style,
        }
        return request.render("vs_hotel_booking_engine.booking_confirmation_page", values)
