# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import datetime
from dateutil.relativedelta import relativedelta
import pytz
import io
import base64
import logging

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class HotelReportWizard(models.TransientModel):
    """
    Intelligent & Flexible Hotel Management Report Wizard.
    Provides unified selection of operational, financial, and management reports
    with dynamic cascading structure filters, flexible date ranges, and multi-format outputs.
    """
    _name = "hotel.report.wizard"
    _description = "Hotel Management Report Wizard"

    # -------------------------------------------------------------------------
    # 1. REPORT SELECTION
    # -------------------------------------------------------------------------
    report_category = fields.Selection(
        [
            ("reservations", "Reservations & Front Desk"),
            ("occupancy", "Room Occupancy & Performance"),
            ("financial", "Billing & Financial Revenue"),
            ("agent", "Travel Agent Commissions"),
            ("operations", "Housekeeping & Maintenance Operations"),
        ],
        string="Report Category",
        required=True,
        default="reservations",
    )

    report_type = fields.Selection(
        [
            ("reservation_register", "Reservation Register & Analysis"),
            ("frontdesk_movements", "Front Desk Daily Operations (Movements & In-House)"),
            ("occupancy_performance", "Room Occupancy & KPI Performance (ADR / RevPAR)"),
            ("financial_revenue", "Folio Revenue & Financial Summary"),
            ("agent_commissions", "Travel Agent Commission Summary"),
            ("operations_summary", "Operations Summary (Housekeeping & Maintenance)"),
        ],
        string="Report Type",
        required=True,
        default="reservation_register",
    )

    # -------------------------------------------------------------------------
    # 2. HIERARCHICAL STRUCTURE FILTERS
    # -------------------------------------------------------------------------
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    hotel_id = fields.Many2one(
        "hotel.hotel",
        string="Hotel",
        required=True,
        default=lambda self: self.env["hotel.hotel"].search([
            "|", ("company_id", "=", False), ("company_id", "=", self.env.company.id)
        ], limit=1),
    )

    building_id = fields.Many2one(
        "hotel.building",
        string="Building",
        domain="[('hotel_id', '=', hotel_id)]",
    )

    floor_id = fields.Many2one(
        "hotel.building.floor",
        string="Floor",
        domain="[('building_id', '=', building_id)]",
    )

    room_category_id = fields.Many2one(
        "hotel.room.category",
        string="Room Type",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    room_id = fields.Many2one(
        "hotel.room",
        string="Specific Room",
    )

    # -------------------------------------------------------------------------
    # 3. DATE RANGE PRESETS & CONFIGURATION
    # -------------------------------------------------------------------------
    date_preset = fields.Selection(
        [
            ("today", "Today"),
            ("yesterday", "Yesterday"),
            ("this_week", "This Week"),
            ("last_week", "Last Week"),
            ("this_month", "This Month"),
            ("last_month", "Last Month"),
            ("this_quarter", "This Quarter"),
            ("last_quarter", "Last Quarter"),
            ("this_year", "This Year"),
            ("last_year", "Last Year"),
            ("custom", "Custom Date Range"),
        ],
        string="Date Range Preset",
        default="this_month",
        required=True,
    )

    date_from = fields.Date(
        string="From Date",
        required=True,
        default=fields.Date.context_today,
    )

    date_to = fields.Date(
        string="To Date",
        required=True,
        default=fields.Date.context_today,
    )

    date_filter_type = fields.Selection(
        [
            ("check_in", "Check-in (Arrival) Date"),
            ("booking_date", "Booking Creation Date"),
            ("check_out", "Check-out (Departure) Date"),
        ],
        string="Date Evaluation Basis",
        default="check_in",
        help="Determines which date field on reservations is compared against the selected range.",
    )

    use_time_filter = fields.Boolean(
        string="Filter by Shift / Hours",
        default=False,
        help="Enable to specify hours of the day or select an operational shift.",
    )
    time_preset = fields.Selection(
        [
            ("all_day", "Full Day (00:00 - 23:59)"),
            ("morning", "Morning Shift (07:00 - 15:00)"),
            ("evening", "Evening Shift (15:00 - 23:00)"),
            ("night", "Night Shift (23:00 - 07:00)"),
            ("custom", "Custom Hours"),
        ],
        string="Shift Preset",
        default="all_day",
    )
    time_from = fields.Float(
        string="From Time",
        default=0.0,
    )
    time_to = fields.Float(
        string="To Time",
        default=23.99,
    )

    # -------------------------------------------------------------------------
    # 4. CONTEXTUAL DYNAMIC FILTERS
    # -------------------------------------------------------------------------
    reservation_status = fields.Selection(
        [
            ("all", "All Statuses (Excl. Draft)"),
            ("confirmed", "Confirmed"),
            ("reserved", "Reserved"),
            ("checked_in", "Checked In"),
            ("checked_out", "Checked Out"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
            ("no_show", "No Show"),
        ],
        string="Reservation Status",
        default="all",
    )

    booking_source = fields.Selection(
        [
            ("all", "All Booking Sources"),
            ("walk_in", "Walk-in"),
            ("phone", "Phone"),
            ("email", "Email"),
            ("website", "Website"),
            ("booking", "Booking.com"),
            ("airbnb", "Airbnb"),
            ("expedia", "Expedia"),
            ("travel_agent", "Travel Agent"),
            ("other", "Other"),
        ],
        string="Booking Source",
        default="all",
    )

    agent_id = fields.Many2one(
        "res.partner",
        string="Travel Agent",
        domain="[('is_travel_agent', '=', True)]",
    )

    commission_status = fields.Selection(
        [
            ("all", "All Statuses"),
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("billed", "Billed"),
            ("paid", "Paid"),
        ],
        string="Commission Status",
        default="all",
    )

    folio_state = fields.Selection(
        [
            ("all", "All Active Folios"),
            ("open", "Open"),
            ("partially_paid", "Partially Paid"),
            ("paid", "Paid"),
            ("closed", "Closed"),
        ],
        string="Folio Status",
        default="all",
    )

    operations_scope = fields.Selection(
        [
            ("both", "Both Housekeeping & Maintenance"),
            ("housekeeping", "Housekeeping Only"),
            ("maintenance", "Maintenance Only"),
        ],
        string="Operations Scope",
        default="both",
    )

    staff_id = fields.Many2one(
        "res.partner",
        string="Assigned Staff Member",
        domain="['|', ('is_housekeeping_staff', '=', True), ('is_maintenance_staff', '=', True)]",
    )

    # -------------------------------------------------------------------------
    # 5. OUTPUT FORMAT
    # -------------------------------------------------------------------------
    output_format = fields.Selection(
        [
            ("pdf", "PDF Document (Printable)"),
            ("xlsx", "Excel Spreadsheet (.xlsx)"),
            ("view", "Interactive Odoo View (Drilldown)"),
        ],
        string="Output Format",
        default="pdf",
        required=True,
    )

    # -------------------------------------------------------------------------
    # ONCHANGES & CASCADING LOGIC
    # -------------------------------------------------------------------------
    @api.onchange("report_category")
    def _onchange_report_category(self):
        category_map = {
            "reservations": "reservation_register",
            "occupancy": "occupancy_performance",
            "financial": "financial_revenue",
            "agent": "agent_commissions",
            "operations": "operations_summary",
        }
        self.report_type = category_map.get(self.report_category, "reservation_register")

    @api.onchange("hotel_id")
    def _onchange_hotel_id(self):
        if self.building_id and self.building_id.hotel_id != self.hotel_id:
            self.building_id = False
        if self.room_id and self.room_id.hotel_id != self.hotel_id:
            self.room_id = False

    @api.onchange("building_id")
    def _onchange_building_id(self):
        if self.floor_id and self.floor_id.building_id != self.building_id:
            self.floor_id = False
        if self.room_id and self.room_id.building_id != self.building_id:
            self.room_id = False

    @api.onchange("floor_id")
    def _onchange_floor_id(self):
        if self.room_id and self.room_id.floor_id != self.floor_id:
            self.room_id = False

    @api.onchange("room_category_id")
    def _onchange_room_category_id(self):
        if self.room_id and self.room_id.room_category_id != self.room_category_id:
            self.room_id = False

    @api.onchange("date_preset")
    def _onchange_date_preset(self):
        today = fields.Date.context_today(self)
        if self.date_preset == "today":
            self.date_from = today
            self.date_to = today
        elif self.date_preset == "yesterday":
            yest = today - datetime.timedelta(days=1)
            self.date_from = yest
            self.date_to = yest
        elif self.date_preset == "this_week":
            start_week = today - datetime.timedelta(days=today.weekday())
            self.date_from = start_week
            self.date_to = start_week + datetime.timedelta(days=6)
        elif self.date_preset == "last_week":
            start_last_week = today - datetime.timedelta(days=today.weekday() + 7)
            self.date_from = start_last_last_week = start_last_week
            self.date_to = start_last_week + datetime.timedelta(days=6)
        elif self.date_preset == "this_month":
            self.date_from = today.replace(day=1)
            next_month = (today.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
            self.date_to = next_month - datetime.timedelta(days=1)
        elif self.date_preset == "last_month":
            first_this_month = today.replace(day=1)
            last_last_month = first_this_month - datetime.timedelta(days=1)
            self.date_from = last_last_month.replace(day=1)
            self.date_to = last_last_month
        elif self.date_preset == "this_quarter":
            quarter = (today.month - 1) // 3 + 1
            first_month_q = (quarter - 1) * 3 + 1
            self.date_from = datetime.date(today.year, first_month_q, 1)
            last_month_q = first_month_q + 2
            next_q_month = (datetime.date(today.year, last_month_q, 28) + datetime.timedelta(days=4)).replace(day=1)
            self.date_to = next_q_month - datetime.timedelta(days=1)
        elif self.date_preset == "last_quarter":
            quarter = (today.month - 1) // 3 + 1
            if quarter == 1:
                last_q_year = today.year - 1
                first_month_q = 10
            else:
                last_q_year = today.year
                first_month_q = (quarter - 2) * 3 + 1
            self.date_from = datetime.date(last_q_year, first_month_q, 1)
            last_month_q = first_month_q + 2
            next_q_month = (datetime.date(last_q_year, last_month_q, 28) + datetime.timedelta(days=4)).replace(day=1)
            self.date_to = next_q_month - datetime.timedelta(days=1)
        elif self.date_preset == "this_year":
            self.date_from = datetime.date(today.year, 1, 1)
            self.date_to = datetime.date(today.year, 12, 31)
        elif self.date_preset == "last_year":
            self.date_from = datetime.date(today.year - 1, 1, 1)
            self.date_to = datetime.date(today.year - 1, 12, 31)

    @api.onchange("time_preset")
    def _onchange_time_preset(self):
        if self.time_preset == "all_day":
            self.time_from = 0.0
            self.time_to = 23.99
        elif self.time_preset == "morning":
            self.time_from = 7.0
            self.time_to = 15.0
        elif self.time_preset == "evening":
            self.time_from = 15.0
            self.time_to = 23.0
        elif self.time_preset == "night":
            self.time_from = 23.0
            self.time_to = 7.0

    # -------------------------------------------------------------------------
    # TIMEZONE & DATETIME HELPERS
    # -------------------------------------------------------------------------
    def _get_tz(self):
        tz_name = self.hotel_id.timezone or self.env.user.tz or "UTC"
        try:
            return pytz.timezone(tz_name)
        except Exception:
            return pytz.UTC

    def _get_datetime_bounds_utc(self):
        """Converts local date_from and date_to (with optional time range) into UTC datetimes."""
        tz = self._get_tz()
        if self.use_time_filter:
            h_from = int(self.time_from)
            m_from = int((self.time_from - h_from) * 60)
            h_to = int(self.time_to)
            m_to = int((self.time_to - h_to) * 60)
            t_from = datetime.time(min(max(h_from, 0), 23), min(max(m_from, 0), 59))
            t_to = datetime.time(min(max(h_to, 0), 23), min(max(m_to, 0), 59))
            dt_from = tz.localize(datetime.datetime.combine(self.date_from, t_from))
            dt_to = tz.localize(datetime.datetime.combine(self.date_to, t_to))
        else:
            dt_from = tz.localize(datetime.datetime.combine(self.date_from, datetime.time.min))
            dt_to = tz.localize(datetime.datetime.combine(self.date_to, datetime.time.max))
        return dt_from.astimezone(pytz.UTC).replace(tzinfo=None), dt_to.astimezone(pytz.UTC).replace(tzinfo=None)

    # -------------------------------------------------------------------------
    # DATA EXTRACTION ENGINES
    # -------------------------------------------------------------------------
    def get_report_data(self):
        """Dispatches data extraction to the corresponding report engine."""
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("From Date cannot be later than To Date."))

        dispatch = {
            "reservation_register": self._get_reservation_register_data,
            "frontdesk_movements": self._get_frontdesk_movements_data,
            "occupancy_performance": self._get_occupancy_performance_data,
            "financial_revenue": self._get_financial_revenue_data,
            "agent_commissions": self._get_agent_commissions_data,
            "operations_summary": self._get_operations_summary_data,
        }
        engine = dispatch.get(self.report_type)
        if not engine:
            raise UserError(_("Unknown report type: %s", self.report_type))
        return engine()

    # 1. RESERVATION REGISTER
    def _get_reservation_register_data(self):
        dt_from, dt_to = self._get_datetime_bounds_utc()
        domain = [("hotel_id", "=", self.hotel_id.id)]

        if self.date_filter_type == "check_in":
            domain += [("check_in", ">=", dt_from), ("check_in", "<=", dt_to)]
        elif self.date_filter_type == "check_out":
            domain += [("check_out", ">=", dt_from), ("check_out", "<=", dt_to)]
        else:
            domain += [("booking_date", ">=", dt_from), ("booking_date", "<=", dt_to)]

        if self.reservation_status != "all":
            domain.append(("state", "=", self.reservation_status))
        else:
            domain.append(("state", "!=", "draft"))

        if self.booking_source != "all":
            domain.append(("booking_source", "=", self.booking_source))

        if self.agent_id:
            domain.append(("agent_id", "=", self.agent_id.id))

        reservations = self.env["hotel.reservation"].search(domain, order="check_in asc, id asc")

        # Further filter by structure if specified
        if self.building_id or self.floor_id or self.room_category_id or self.room_id:
            filtered_res = self.env["hotel.reservation"]
            for res in reservations:
                rooms = res.room_booking_ids.mapped("room_id")
                if self.room_id and self.room_id not in rooms:
                    continue
                if self.room_category_id and not any(r.room_category_id == self.room_category_id for r in rooms):
                    continue
                if self.floor_id and not any(r.floor_id == self.floor_id for r in rooms):
                    continue
                if self.building_id and not any(r.building_id == self.building_id for r in rooms):
                    continue
                filtered_res |= res
            reservations = filtered_res

        records = []
        total_nights = 0
        total_gross = 0.0
        total_discount = 0.0
        total_net_room = 0.0
        total_tax = 0.0
        total_services = 0.0
        total_amount = 0.0

        for r in reservations:
            ci_str = r.check_in_formatted or (r.check_in.strftime("%Y-%m-%d %H:%M") if r.check_in else "")
            co_str = r.check_out_formatted or (r.check_out.strftime("%Y-%m-%d %H:%M") if r.check_out else "")
            records.append({
                "name": r.name,
                "guest_name": r.partner_id.name,
                "guest_phone": r.partner_id.phone or "",
                "rooms": r.booked_rooms_display or "-",
                "source": dict(r._fields["booking_source"].selection).get(r.booking_source, r.booking_source),
                "state": dict(r._fields["state"].selection).get(r.state, r.state),
                "check_in": ci_str,
                "check_out": co_str,
                "nights": r.night_count,
                "room_amount": r.room_amount,
                "discount_amount": r.discount_amount,
                "net_room_amount": r.net_room_amount,
                "service_amount": r.service_amount,
                "tax_amount": r.tax_amount,
                "total_amount": r.total_amount,
                "payment_status": dict(r._fields["payment_status"].selection).get(r.payment_status, r.payment_status),
                "currency": r.currency_id,
            })
            total_nights += r.night_count
            total_gross += r.room_amount
            total_discount += r.discount_amount
            total_net_room += r.net_room_amount
            total_services += r.service_amount
            total_tax += r.tax_amount
            total_amount += r.total_amount

        return {
            "title": _("Reservation Register & Analysis"),
            "report_type": "reservation_register",
            "hotel": self.hotel_id,
            "currency": self.hotel_id.currency_id or self.company_id.currency_id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "filter_desc": f"Basis: {dict(self._fields['date_filter_type'].selection).get(self.date_filter_type)} | Status: {self.reservation_status.title()} | Source: {self.booking_source.title()}",
            "records": records,
            "kpis": {
                "count": len(records),
                "total_nights": total_nights,
                "total_gross": total_gross,
                "total_discount": total_discount,
                "total_net_room": total_net_room,
                "total_services": total_services,
                "total_tax": total_tax,
                "total_amount": total_amount,
            }
        }

    # 2. FRONT DESK MOVEMENTS & IN-HOUSE
    def _get_frontdesk_movements_data(self):
        target_date = self.date_from
        tz = self._get_tz()
        dt_day_start = tz.localize(datetime.datetime.combine(target_date, datetime.time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        dt_day_end = tz.localize(datetime.datetime.combine(target_date, datetime.time.max)).astimezone(pytz.UTC).replace(tzinfo=None)

        base_domain = [("hotel_id", "=", self.hotel_id.id)]

        # 1. Expected Arrivals
        arrivals_res = self.env["hotel.reservation"].search(
            base_domain + [
                ("check_in", ">=", dt_day_start),
                ("check_in", "<=", dt_day_end),
                ("state", "in", ["confirmed", "reserved"]),
            ],
            order="check_in asc",
        )
        arrivals = []
        for r in arrivals_res:
            arrivals.append({
                "res_name": r.name,
                "guest": r.partner_id.name,
                "phone": r.partner_id.phone or "",
                "rooms": r.booked_rooms_display or "-",
                "expected_time": r.check_in_formatted or r.check_in.strftime("%H:%M"),
                "nights": r.night_count,
                "adults": r.adult_count,
                "children": r.child_count,
                "source": dict(r._fields["booking_source"].selection).get(r.booking_source, r.booking_source),
                "balance": r.folio_balance,
            })

        # 2. In-House Guests
        in_house_res = self.env["hotel.reservation"].search(
            base_domain + [
                ("state", "=", "checked_in"),
            ],
            order="check_out asc",
        )
        in_house = []
        for r in in_house_res:
            in_house.append({
                "res_name": r.name,
                "guest": r.partner_id.name,
                "phone": r.partner_id.phone or "",
                "rooms": r.booked_rooms_display or "-",
                "check_in": r.check_in_formatted or r.check_in.strftime("%Y-%m-%d"),
                "check_out": r.check_out_formatted or r.check_out.strftime("%Y-%m-%d"),
                "adults": r.adult_count,
                "children": r.child_count,
                "folio_name": r.folio_id.name if r.folio_id else "-",
                "balance": r.folio_balance,
            })

        # 3. Expected Departures
        departures_res = self.env["hotel.reservation"].search(
            base_domain + [
                ("check_out", ">=", dt_day_start),
                ("check_out", "<=", dt_day_end),
                ("state", "=", "checked_in"),
            ],
            order="check_out asc",
        )
        departures = []
        for r in departures_res:
            departures.append({
                "res_name": r.name,
                "guest": r.partner_id.name,
                "phone": r.partner_id.phone or "",
                "rooms": r.booked_rooms_display or "-",
                "checkout_time": r.check_out_formatted or r.check_out.strftime("%H:%M"),
                "folio_name": r.folio_id.name if r.folio_id else "-",
                "payment_status": dict(r._fields["payment_status"].selection).get(r.payment_status, r.payment_status),
                "balance": r.folio_balance,
            })

        return {
            "title": _("Front Desk Daily Operations Sheet"),
            "report_type": "frontdesk_movements",
            "hotel": self.hotel_id,
            "currency": self.hotel_id.currency_id or self.company_id.currency_id,
            "target_date": target_date,
            "date_from": target_date,
            "date_to": target_date,
            "arrivals": arrivals,
            "in_house": in_house,
            "departures": departures,
            "kpis": {
                "arrivals_count": len(arrivals),
                "in_house_count": len(in_house),
                "departures_count": len(departures),
            }
        }

    # 3. ROOM OCCUPANCY & KPI PERFORMANCE (ADR & RevPAR)
    def _get_occupancy_performance_data(self):
        tz = self._get_tz()
        date_from = self.date_from
        date_to = self.date_to
        total_days = (date_to - date_from).days + 1

        # Match rooms
        room_domain = [("hotel_id", "=", self.hotel_id.id), ("active", "=", True)]
        if self.building_id:
            room_domain.append(("building_id", "=", self.building_id.id))
        if self.floor_id:
            room_domain.append(("floor_id", "=", self.floor_id.id))
        if self.room_category_id:
            room_domain.append(("room_category_id", "=", self.room_category_id.id))
        if self.room_id:
            room_domain.append(("id", "=", self.room_id.id))

        rooms = self.env["hotel.room"].search(room_domain)
        operational_rooms_count = len(rooms)
        total_available_room_nights = operational_rooms_count * total_days

        # Match bookings overlapping window
        dt_start_utc, dt_end_utc = self._get_datetime_bounds_utc()
        booking_domain = [
            ("room_id", "in", rooms.ids),
            ("state", "in", ["checked_in", "checked_out", "completed", "reserved"]),
            ("check_in", "<", dt_end_utc),
            ("check_out", ">", dt_start_utc),
        ]
        bookings = self.env["hotel.room.booking"].search(booking_domain)

        # Calculate occupied room nights per category
        category_stats = {}
        for room in rooms:
            cat = room.room_category_id
            if cat not in category_stats:
                category_stats[cat] = {
                    "category": cat.name or _("Standard"),
                    "total_rooms": 0,
                    "available_nights": 0,
                    "occupied_nights": 0,
                    "room_revenue": 0.0,
                }
            category_stats[cat]["total_rooms"] += 1
            category_stats[cat]["available_nights"] += total_days

        total_occupied_nights = 0
        total_room_revenue = 0.0

        for b in bookings:
            # Localize checkin/out to hotel timezone dates
            b_ci = pytz.UTC.localize(b.check_in).astimezone(tz).date() if b.check_in else date_from
            b_co = pytz.UTC.localize(b.check_out).astimezone(tz).date() if b.check_out else date_to

            # Overlap nights: intersection of [b_ci, b_co) and [date_from, date_to + 1)
            stay_start = max(b_ci, date_from)
            stay_end = min(b_co, date_to + datetime.timedelta(days=1))
            nights_in_window = max(0, (stay_end - stay_start).days)

            if nights_in_window > 0:
                total_occupied_nights += nights_in_window
                cat = b.room_id.room_category_id
                if cat in category_stats:
                    category_stats[cat]["occupied_nights"] += nights_in_window

                # Pro-rate net room revenue for the nights in window
                total_b_nights = max(1, (b_co - b_ci).days)
                b_res = b.reservation_id
                res_net_room = b_res.net_room_amount if b_res else 0.0
                # If reservation has multiple room bookings, split proportionally
                room_booking_count = len(b_res.room_booking_ids) if b_res else 1
                b_revenue = (res_net_room / room_booking_count) * (nights_in_window / total_b_nights)
                total_room_revenue += b_revenue
                if cat in category_stats:
                    category_stats[cat]["room_revenue"] += b_revenue

        category_records = []
        for cat, data in category_stats.items():
            avail = data["available_nights"]
            occ = data["occupied_nights"]
            occ_rate = (occ / avail * 100.0) if avail > 0 else 0.0
            rev = data["room_revenue"]
            adr = (rev / occ) if occ > 0 else 0.0
            revpar = (rev / avail) if avail > 0 else 0.0
            category_records.append({
                "category": data["category"],
                "total_rooms": data["total_rooms"],
                "available_nights": avail,
                "occupied_nights": occ,
                "occupancy_rate": occ_rate,
                "room_revenue": rev,
                "adr": adr,
                "revpar": revpar,
            })

        overall_occ_rate = (total_occupied_nights / total_available_room_nights * 100.0) if total_available_room_nights > 0 else 0.0
        overall_adr = (total_room_revenue / total_occupied_nights) if total_occupied_nights > 0 else 0.0
        overall_revpar = (total_room_revenue / total_available_room_nights) if total_available_room_nights > 0 else 0.0

        return {
            "title": _("Room Occupancy & KPI Performance Report"),
            "report_type": "occupancy_performance",
            "hotel": self.hotel_id,
            "currency": self.hotel_id.currency_id or self.company_id.currency_id,
            "date_from": date_from,
            "date_to": date_to,
            "days_count": total_days,
            "categories": category_records,
            "kpis": {
                "total_rooms": operational_rooms_count,
                "available_nights": total_available_room_nights,
                "occupied_nights": total_occupied_nights,
                "occupancy_rate": overall_occ_rate,
                "total_room_revenue": total_room_revenue,
                "adr": overall_adr,
                "revpar": overall_revpar,
            }
        }

    # 4. FINANCIAL & FOLIO REVENUE
    def _get_financial_revenue_data(self):
        dt_from, dt_to = self._get_datetime_bounds_utc()
        domain = [("hotel_id", "=", self.hotel_id.id)]

        if self.folio_state != "all":
            domain.append(("state", "=", self.folio_state))
        else:
            domain.append(("state", "!=", "cancelled"))

        folios = self.env["hotel.guest.folio"].search(domain, order="id desc")

        # Filter by line dates or folio stay dates intersecting range
        records = []
        charge_summary = {
            "room": 0.0,
            "service": 0.0,
            "minibar": 0.0,
            "restaurant": 0.0,
            "laundry": 0.0,
            "spa": 0.0,
            "extra": 0.0,
            "tax": 0.0,
            "discount": 0.0,
        }
        total_untaxed = 0.0
        total_tax = 0.0
        total_discount = 0.0
        total_billed = 0.0
        total_paid = 0.0
        total_balance = 0.0

        for f in folios:
            # Check date intersection via lines or folio check_in/check_out
            lines = f.line_ids.filtered(lambda l: l.date >= dt_from and l.date <= dt_to)
            if not lines and not (f.check_in and f.check_in <= dt_to and f.check_out and f.check_out >= dt_from):
                continue

            for line in f.line_ids:
                if line.charge_type in charge_summary:
                    charge_summary[line.charge_type] += line.total_amount

            records.append({
                "name": f.name,
                "guest": f.partner_id.name,
                "reservation": f.reservation_id.name if f.reservation_id else "-",
                "check_in": f.check_in.strftime("%Y-%m-%d") if f.check_in else "-",
                "check_out": f.check_out.strftime("%Y-%m-%d") if f.check_out else "-",
                "state": dict(f._fields["state"].selection).get(f.state, f.state),
                "untaxed": f.amount_untaxed,
                "tax": f.tax_amount,
                "discount": f.discount_amount,
                "total": f.total_amount,
                "paid": f.paid_amount,
                "balance": f.balance_amount,
                "invoice": f.invoice_id.name if f.invoice_id else "-",
                "invoice_state": dict(f.invoice_id._fields["payment_state"].selection).get(f.invoice_id.payment_state, "-") if f.invoice_id else "-",
            })

            total_untaxed += f.amount_untaxed
            total_tax += f.tax_amount
            total_discount += f.discount_amount
            total_billed += f.total_amount
            total_paid += f.paid_amount
            total_balance += f.balance_amount

        return {
            "title": _("Folio Revenue & Financial Summary"),
            "report_type": "financial_revenue",
            "hotel": self.hotel_id,
            "currency": self.hotel_id.currency_id or self.company_id.currency_id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "records": records,
            "charges": charge_summary,
            "kpis": {
                "folio_count": len(records),
                "total_untaxed": total_untaxed,
                "total_tax": total_tax,
                "total_discount": total_discount,
                "total_billed": total_billed,
                "total_paid": total_paid,
                "total_balance": total_balance,
            }
        }

    # 5. TRAVEL AGENT COMMISSIONS
    def _get_agent_commissions_data(self):
        domain = [("company_id", "=", self.company_id.id)]
        if self.hotel_id:
            domain.append(("reservation_id.hotel_id", "=", self.hotel_id.id))

        domain += [("date", ">=", self.date_from), ("date", "<=", self.date_to)]

        if self.agent_id:
            domain.append(("agent_id", "=", self.agent_id.id))

        if self.commission_status != "all":
            domain.append(("state", "=", self.commission_status))
        else:
            domain.append(("state", "!=", "cancelled"))

        commissions = self.env["hotel.agent.commission"].search(domain, order="date asc, id asc")

        records = []
        total_base = 0.0
        total_net_room = 0.0
        total_commission = 0.0
        total_paid_commission = 0.0
        total_unpaid_commission = 0.0

        for c in commissions:
            is_paid = (c.state == "paid" or (c.invoice_id and c.invoice_id.payment_state in ("paid", "in_payment")))
            records.append({
                "name": c.name,
                "date": c.date.strftime("%Y-%m-%d"),
                "agent_name": c.agent_id.name,
                "reservation": c.reservation_id.name if c.reservation_id else "-",
                "folio": c.folio_id.name if c.folio_id else "-",
                "state": dict(c._fields["state"].selection).get(c.state, c.state),
                "base_amount": c.total_base_amount,
                "discount_amount": c.total_discount_amount,
                "net_room_amount": c.total_room_amount,
                "commission_amount": c.total_commission_amount,
                "invoice": c.invoice_id.name if c.invoice_id else "-",
                "is_paid": is_paid,
            })
            total_base += c.total_base_amount
            total_net_room += c.total_room_amount
            total_commission += c.total_commission_amount
            if is_paid:
                total_paid_commission += c.total_commission_amount
            else:
                total_unpaid_commission += c.total_commission_amount

        return {
            "title": _("Travel Agent Commission Summary"),
            "report_type": "agent_commissions",
            "hotel": self.hotel_id,
            "currency": self.company_id.currency_id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "records": records,
            "kpis": {
                "commission_count": len(records),
                "total_base": total_base,
                "total_net_room": total_net_room,
                "total_commission": total_commission,
                "total_paid_commission": total_paid_commission,
                "total_unpaid_commission": total_unpaid_commission,
            }
        }

    # 6. OPERATIONS SUMMARY (HOUSEKEEPING & MAINTENANCE)
    def _get_operations_summary_data(self):
        dt_from, dt_to = self._get_datetime_bounds_utc()
        hk_records = []
        maint_records = []

        hk_domain = [
            ("hotel_id", "=", self.hotel_id.id),
            ("scheduled_date", ">=", dt_from),
            ("scheduled_date", "<=", dt_to),
        ]
        maint_domain = [
            ("hotel_id", "=", self.hotel_id.id),
            ("scheduled_date", ">=", dt_from),
            ("scheduled_date", "<=", dt_to),
        ]

        if self.building_id:
            hk_domain.append(("building_id", "=", self.building_id.id))
            maint_domain.append(("building_id", "=", self.building_id.id))
        if self.floor_id:
            hk_domain.append(("floor_id", "=", self.floor_id.id))
            maint_domain.append(("floor_id", "=", self.floor_id.id))
        if self.room_id:
            hk_domain.append(("room_id", "=", self.room_id.id))
            maint_domain.append(("room_id", "=", self.room_id.id))
        if self.staff_id:
            hk_domain.append(("assigned_to", "=", self.staff_id.id))
            maint_domain.append(("assigned_to", "=", self.staff_id.id))

        if self.operations_scope in ("both", "housekeeping"):
            tasks = self.env["hotel.housekeeping"].search(hk_domain, order="scheduled_date asc")
            for t in tasks:
                hk_records.append({
                    "name": t.name,
                    "room": t.room_id.room_number,
                    "type": dict(t._fields["housekeeping_type"].selection).get(t.housekeeping_type, t.housekeeping_type),
                    "priority": dict(t._fields["priority"].selection).get(t.priority, t.priority),
                    "scheduled": t.scheduled_date.strftime("%Y-%m-%d %H:%M") if t.scheduled_date else "-",
                    "assigned_to": t.assigned_to.name if t.assigned_to else "-",
                    "state": dict(t._fields["state"].selection).get(t.state, t.state),
                    "completed_at": t.completed_at.strftime("%Y-%m-%d %H:%M") if t.completed_at else "-",
                })

        if self.operations_scope in ("both", "maintenance"):
            requests = self.env["hotel.maintenance"].search(maint_domain, order="scheduled_date asc")
            for m in requests:
                maint_records.append({
                    "name": m.name,
                    "room": m.room_id.room_number,
                    "type": dict(m._fields["maintenance_type"].selection).get(m.maintenance_type, m.maintenance_type),
                    "priority": dict(m._fields["priority"].selection).get(m.priority, m.priority),
                    "scheduled": m.scheduled_date.strftime("%Y-%m-%d %H:%M") if m.scheduled_date else "-",
                    "assigned_to": m.assigned_to.name if m.assigned_to else "-",
                    "state": dict(m._fields["state"].selection).get(m.state, m.state),
                    "completed_at": m.completed_at.strftime("%Y-%m-%d %H:%M") if m.completed_at else "-",
                })

        hk_done = sum(1 for x in hk_records if x["state"] == "Done")
        maint_done = sum(1 for x in maint_records if x["state"] == "Completed")

        return {
            "title": _("Hotel Operations Summary (Housekeeping & Maintenance)"),
            "report_type": "operations_summary",
            "hotel": self.hotel_id,
            "currency": self.company_id.currency_id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "housekeeping": hk_records,
            "maintenance": maint_records,
            "kpis": {
                "hk_total": len(hk_records),
                "hk_completed": hk_done,
                "hk_pending": len(hk_records) - hk_done,
                "maint_total": len(maint_records),
                "maint_completed": maint_done,
                "maint_pending": len(maint_records) - maint_done,
            }
        }

    # -------------------------------------------------------------------------
    # OUTPUT GENERATION DISPATCHERS
    # -------------------------------------------------------------------------
    def action_generate_report(self):
        """Main Action: branches according to output_format."""
        self.ensure_one()
        if self.output_format == "pdf":
            return self.action_print_pdf()
        elif self.output_format == "xlsx":
            return self.action_export_xlsx()
        elif self.output_format == "view":
            return self.action_view_records()

    def action_print_pdf(self):
        """Generates and downloads the QWeb PDF report."""
        self.ensure_one()
        report_action = self.env.ref("vs_hotel_management.action_report_hotel_management", raise_if_not_found=False)
        if not report_action:
            raise UserError(_("Report action 'vs_hotel_management.action_report_hotel_management' not found."))
        return report_action.report_action(self)

    def action_view_records(self):
        """Redirects to interactive native Odoo views with matching pre-filters."""
        self.ensure_one()
        dt_from, dt_to = self._get_datetime_bounds_utc()

        if self.report_type in ("reservation_register", "frontdesk_movements"):
            domain = [("hotel_id", "=", self.hotel_id.id)]
            if self.date_filter_type == "check_in":
                domain += [("check_in", ">=", dt_from), ("check_in", "<=", dt_to)]
            elif self.date_filter_type == "check_out":
                domain += [("check_out", ">=", dt_from), ("check_out", "<=", dt_to)]
            else:
                domain += [("booking_date", ">=", dt_from), ("booking_date", "<=", dt_to)]
            return {
                "name": _("Matching Reservations"),
                "type": "ir.actions.act_window",
                "res_model": "hotel.reservation",
                "view_mode": "list,kanban,form,pivot,graph",
                "domain": domain,
                "context": {"search_default_group_by_state": 1},
            }

        elif self.report_type == "occupancy_performance":
            return {
                "name": _("Room Bookings Performance"),
                "type": "ir.actions.act_window",
                "res_model": "hotel.room.booking",
                "view_mode": "pivot,graph,calendar,list,form",
                "domain": [("hotel_id", "=", self.hotel_id.id), ("check_in", "<=", dt_to), ("check_out", ">=", dt_from)],
                "context": {"search_default_group_by_room_category": 1},
            }

        elif self.report_type == "financial_revenue":
            return {
                "name": _("Guest Folios Financial Analysis"),
                "type": "ir.actions.act_window",
                "res_model": "hotel.guest.folio",
                "view_mode": "list,kanban,form",
                "domain": [("hotel_id", "=", self.hotel_id.id)],
                "context": {"search_default_group_by_state": 1},
            }

        elif self.report_type == "agent_commissions":
            return {
                "name": _("Agent Commissions"),
                "type": "ir.actions.act_window",
                "res_model": "hotel.agent.commission",
                "view_mode": "list,form",
                "domain": [("company_id", "=", self.company_id.id), ("date", ">=", self.date_from), ("date", "<=", self.date_to)],
                "context": {"search_default_group_by_agent": 1},
            }

        elif self.report_type == "operations_summary":
            return {
                "name": _("Housekeeping Operations"),
                "type": "ir.actions.act_window",
                "res_model": "hotel.housekeeping",
                "view_mode": "list,kanban,form,calendar",
                "domain": [("hotel_id", "=", self.hotel_id.id), ("scheduled_date", ">=", dt_from), ("scheduled_date", "<=", dt_to)],
                "context": {"search_default_group_by_state": 1},
            }

    # -------------------------------------------------------------------------
    # EXCEL (XLSX) GENERATION ENGINE
    # -------------------------------------------------------------------------
    def action_export_xlsx(self):
        """Builds a formatted professional Excel workbook using xlsxwriter."""
        self.ensure_one()
        if not xlsxwriter:
            raise UserError(_("The Python 'xlsxwriter' library is not available in the server environment."))

        data = self.get_report_data()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet(_("Report"))
        worksheet.set_paper(9)  # A4
        worksheet.set_margins(0.5, 0.5, 0.5, 0.5)

        # Styles
        title_fmt = workbook.add_format({
            "bold": True, "font_size": 16, "font_color": "#1A365D", "valign": "vcenter"
        })
        subtitle_fmt = workbook.add_format({
            "italic": True, "font_size": 10, "font_color": "#4A5568", "valign": "vcenter"
        })
        header_fmt = workbook.add_format({
            "bold": True, "font_size": 10, "bg_color": "#2B6CB0", "font_color": "#FFFFFF",
            "border": 1, "border_color": "#CBD5E0", "align": "center", "valign": "vcenter"
        })
        cell_fmt = workbook.add_format({
            "font_size": 9, "border": 1, "border_color": "#E2E8F0", "valign": "vcenter"
        })
        cell_num_fmt = workbook.add_format({
            "font_size": 9, "border": 1, "border_color": "#E2E8F0", "align": "right",
            "num_format": "#,##0.00", "valign": "vcenter"
        })
        cell_pct_fmt = workbook.add_format({
            "font_size": 9, "border": 1, "border_color": "#E2E8F0", "align": "right",
            "num_format": "0.0%", "valign": "vcenter"
        })
        total_label_fmt = workbook.add_format({
            "bold": True, "font_size": 10, "bg_color": "#EDF2F7", "border": 1,
            "border_color": "#CBD5E0", "align": "left", "valign": "vcenter"
        })
        total_num_fmt = workbook.add_format({
            "bold": True, "font_size": 10, "bg_color": "#EDF2F7", "border": 1,
            "border_color": "#CBD5E0", "align": "right", "num_format": "#,##0.00", "valign": "vcenter"
        })

        # Header section
        worksheet.write(0, 0, data["title"], title_fmt)
        worksheet.write(1, 0, f"Hotel: {self.hotel_id.name} | Period: {self.date_from} to {self.date_to}", subtitle_fmt)
        row = 3

        report_type = data["report_type"]

        if report_type == "reservation_register":
            headers = ["Ref", "Guest Name", "Phone", "Rooms", "Source", "Check-in", "Check-out", "Nights", "Status", "Room Total", "Discount", "Net Room", "Services", "Tax", "Grand Total", "Payment"]
            for col, h in enumerate(headers):
                worksheet.write(row, col, h, header_fmt)
            row += 1

            for rec in data["records"]:
                worksheet.write(row, 0, rec["name"], cell_fmt)
                worksheet.write(row, 1, rec["guest_name"], cell_fmt)
                worksheet.write(row, 2, rec["guest_phone"], cell_fmt)
                worksheet.write(row, 3, rec["rooms"], cell_fmt)
                worksheet.write(row, 4, rec["source"], cell_fmt)
                worksheet.write(row, 5, rec["check_in"], cell_fmt)
                worksheet.write(row, 6, rec["check_out"], cell_fmt)
                worksheet.write(row, 7, rec["nights"], cell_fmt)
                worksheet.write(row, 8, rec["state"], cell_fmt)
                worksheet.write(row, 9, rec["room_amount"], cell_num_fmt)
                worksheet.write(row, 10, rec["discount_amount"], cell_num_fmt)
                worksheet.write(row, 11, rec["net_room_amount"], cell_num_fmt)
                worksheet.write(row, 12, rec["service_amount"], cell_num_fmt)
                worksheet.write(row, 13, rec["tax_amount"], cell_num_fmt)
                worksheet.write(row, 14, rec["total_amount"], cell_num_fmt)
                worksheet.write(row, 15, rec["payment_status"], cell_fmt)
                row += 1

            # Totals
            worksheet.write(row, 0, _("TOTALS"), total_label_fmt)
            for c in range(1, 9):
                worksheet.write(row, c, "", total_label_fmt)
            worksheet.write(row, 9, data["kpis"]["total_gross"], total_num_fmt)
            worksheet.write(row, 10, data["kpis"]["total_discount"], total_num_fmt)
            worksheet.write(row, 11, data["kpis"]["total_net_room"], total_num_fmt)
            worksheet.write(row, 12, data["kpis"]["total_services"], total_num_fmt)
            worksheet.write(row, 13, data["kpis"]["total_tax"], total_num_fmt)
            worksheet.write(row, 14, data["kpis"]["total_amount"], total_num_fmt)
            worksheet.write(row, 15, "", total_label_fmt)

        elif report_type == "occupancy_performance":
            headers = ["Room Category / Type", "Total Rooms", "Available Nights", "Occupied Nights", "Occupancy %", "Net Room Revenue", "ADR", "RevPAR"]
            for col, h in enumerate(headers):
                worksheet.write(row, col, h, header_fmt)
            row += 1

            for c in data["categories"]:
                worksheet.write(row, 0, c["category"], cell_fmt)
                worksheet.write(row, 1, c["total_rooms"], cell_fmt)
                worksheet.write(row, 2, c["available_nights"], cell_fmt)
                worksheet.write(row, 3, c["occupied_nights"], cell_fmt)
                worksheet.write(row, 4, c["occupancy_rate"] / 100.0, cell_pct_fmt)
                worksheet.write(row, 5, c["room_revenue"], cell_num_fmt)
                worksheet.write(row, 6, c["adr"], cell_num_fmt)
                worksheet.write(row, 7, c["revpar"], cell_num_fmt)
                row += 1

            worksheet.write(row, 0, _("OVERALL SUMMARY"), total_label_fmt)
            worksheet.write(row, 1, data["kpis"]["total_rooms"], total_label_fmt)
            worksheet.write(row, 2, data["kpis"]["available_nights"], total_label_fmt)
            worksheet.write(row, 3, data["kpis"]["occupied_nights"], total_label_fmt)
            worksheet.write(row, 4, data["kpis"]["occupancy_rate"] / 100.0, workbook.add_format({"bold": True, "bg_color": "#EDF2F7", "border": 1, "border_color": "#CBD5E0", "align": "right", "num_format": "0.0%"}))
            worksheet.write(row, 5, data["kpis"]["total_room_revenue"], total_num_fmt)
            worksheet.write(row, 6, data["kpis"]["adr"], total_num_fmt)
            worksheet.write(row, 7, data["kpis"]["revpar"], total_num_fmt)

        elif report_type == "financial_revenue":
            headers = ["Folio Ref", "Guest", "Reservation", "Check-in", "Check-out", "Status", "Untaxed", "Tax", "Discount", "Total Billed", "Paid", "Balance", "Invoice Ref", "Invoice State"]
            for col, h in enumerate(headers):
                worksheet.write(row, col, h, header_fmt)
            row += 1

            for rec in data["records"]:
                worksheet.write(row, 0, rec["name"], cell_fmt)
                worksheet.write(row, 1, rec["guest"], cell_fmt)
                worksheet.write(row, 2, rec["reservation"], cell_fmt)
                worksheet.write(row, 3, rec["check_in"], cell_fmt)
                worksheet.write(row, 4, rec["check_out"], cell_fmt)
                worksheet.write(row, 5, rec["state"], cell_fmt)
                worksheet.write(row, 6, rec["untaxed"], cell_num_fmt)
                worksheet.write(row, 7, rec["tax"], cell_num_fmt)
                worksheet.write(row, 8, rec["discount"], cell_num_fmt)
                worksheet.write(row, 9, rec["total"], cell_num_fmt)
                worksheet.write(row, 10, rec["paid"], cell_num_fmt)
                worksheet.write(row, 11, rec["balance"], cell_num_fmt)
                worksheet.write(row, 12, rec["invoice"], cell_fmt)
                worksheet.write(row, 13, rec["invoice_state"], cell_fmt)
                row += 1

            worksheet.write(row, 0, _("TOTALS"), total_label_fmt)
            for c in range(1, 6):
                worksheet.write(row, c, "", total_label_fmt)
            worksheet.write(row, 6, data["kpis"]["total_untaxed"], total_num_fmt)
            worksheet.write(row, 7, data["kpis"]["total_tax"], total_num_fmt)
            worksheet.write(row, 8, data["kpis"]["total_discount"], total_num_fmt)
            worksheet.write(row, 9, data["kpis"]["total_billed"], total_num_fmt)
            worksheet.write(row, 10, data["kpis"]["total_paid"], total_num_fmt)
            worksheet.write(row, 11, data["kpis"]["total_balance"], total_num_fmt)
            worksheet.write(row, 12, "", total_label_fmt)
            worksheet.write(row, 13, "", total_label_fmt)

        elif report_type == "agent_commissions":
            headers = ["Ref", "Date", "Travel Agent", "Reservation", "Folio", "Status", "Base Room Amount", "Discount", "Net Room Amount", "Commission Amount", "Vendor Bill", "Payment"]
            for col, h in enumerate(headers):
                worksheet.write(row, col, h, header_fmt)
            row += 1

            for rec in data["records"]:
                worksheet.write(row, 0, rec["name"], cell_fmt)
                worksheet.write(row, 1, rec["date"], cell_fmt)
                worksheet.write(row, 2, rec["agent_name"], cell_fmt)
                worksheet.write(row, 3, rec["reservation"], cell_fmt)
                worksheet.write(row, 4, rec["folio"], cell_fmt)
                worksheet.write(row, 5, rec["state"], cell_fmt)
                worksheet.write(row, 6, rec["base_amount"], cell_num_fmt)
                worksheet.write(row, 7, rec["discount_amount"], cell_num_fmt)
                worksheet.write(row, 8, rec["net_room_amount"], cell_num_fmt)
                worksheet.write(row, 9, rec["commission_amount"], cell_num_fmt)
                worksheet.write(row, 10, rec["invoice"], cell_fmt)
                worksheet.write(row, 11, _("Paid") if rec["is_paid"] else _("Pending"), cell_fmt)
                row += 1

            worksheet.write(row, 0, _("TOTALS"), total_label_fmt)
            for c in range(1, 6):
                worksheet.write(row, c, "", total_label_fmt)
            worksheet.write(row, 6, data["kpis"]["total_base"], total_num_fmt)
            worksheet.write(row, 7, "", total_label_fmt)
            worksheet.write(row, 8, data["kpis"]["total_net_room"], total_num_fmt)
            worksheet.write(row, 9, data["kpis"]["total_commission"], total_num_fmt)
            worksheet.write(row, 10, "", total_label_fmt)
            worksheet.write(row, 11, "", total_label_fmt)

        elif report_type == "operations_summary":
            # Housekeeping section
            worksheet.write(row, 0, _("HOUSEKEEPING TASKS"), total_label_fmt)
            row += 1
            hk_headers = ["Task Ref", "Room", "Type", "Priority", "Scheduled", "Assigned Staff", "Completed At", "Status"]
            for col, h in enumerate(hk_headers):
                worksheet.write(row, col, h, header_fmt)
            row += 1

            for rec in data["housekeeping"]:
                worksheet.write(row, 0, rec["name"], cell_fmt)
                worksheet.write(row, 1, rec["room"], cell_fmt)
                worksheet.write(row, 2, rec["type"], cell_fmt)
                worksheet.write(row, 3, rec["priority"], cell_fmt)
                worksheet.write(row, 4, rec["scheduled"], cell_fmt)
                worksheet.write(row, 5, rec["assigned_to"], cell_fmt)
                worksheet.write(row, 6, rec["completed_at"], cell_fmt)
                worksheet.write(row, 7, rec["state"], cell_fmt)
                row += 1

            row += 2
            # Maintenance section
            worksheet.write(row, 0, _("MAINTENANCE REQUESTS"), total_label_fmt)
            row += 1
            maint_headers = ["Request Ref", "Room", "Type", "Priority", "Scheduled", "Assigned Technician", "Completed At", "Status"]
            for col, h in enumerate(maint_headers):
                worksheet.write(row, col, h, header_fmt)
            row += 1

            for rec in data["maintenance"]:
                worksheet.write(row, 0, rec["name"], cell_fmt)
                worksheet.write(row, 1, rec["room"], cell_fmt)
                worksheet.write(row, 2, rec["type"], cell_fmt)
                worksheet.write(row, 3, rec["priority"], cell_fmt)
                worksheet.write(row, 4, rec["scheduled"], cell_fmt)
                worksheet.write(row, 5, rec["assigned_to"], cell_fmt)
                worksheet.write(row, 6, rec["completed_at"], cell_fmt)
                worksheet.write(row, 7, rec["state"], cell_fmt)
                row += 1

        elif report_type == "frontdesk_movements":
            # Arrivals
            worksheet.write(row, 0, _("EXPECTED ARRIVALS"), total_label_fmt)
            row += 1
            arr_headers = ["Res Ref", "Guest Name", "Phone", "Rooms", "Expected Time", "Nights", "Adults", "Children", "Source", "Balance"]
            for col, h in enumerate(arr_headers):
                worksheet.write(row, col, h, header_fmt)
            row += 1
            for rec in data["arrivals"]:
                worksheet.write(row, 0, rec["res_name"], cell_fmt)
                worksheet.write(row, 1, rec["guest"], cell_fmt)
                worksheet.write(row, 2, rec["phone"], cell_fmt)
                worksheet.write(row, 3, rec["rooms"], cell_fmt)
                worksheet.write(row, 4, rec["expected_time"], cell_fmt)
                worksheet.write(row, 5, rec["nights"], cell_fmt)
                worksheet.write(row, 6, rec["adults"], cell_fmt)
                worksheet.write(row, 7, rec["children"], cell_fmt)
                worksheet.write(row, 8, rec["source"], cell_fmt)
                worksheet.write(row, 9, rec["balance"], cell_num_fmt)
                row += 1

            row += 2
            # In-House
            worksheet.write(row, 0, _("IN-HOUSE GUESTS"), total_label_fmt)
            row += 1
            in_headers = ["Res Ref", "Guest Name", "Phone", "Rooms", "Check-in", "Check-out", "Adults", "Children", "Folio", "Balance"]
            for col, h in enumerate(in_headers):
                worksheet.write(row, col, h, header_fmt)
            row += 1
            for rec in data["in_house"]:
                worksheet.write(row, 0, rec["res_name"], cell_fmt)
                worksheet.write(row, 1, rec["guest"], cell_fmt)
                worksheet.write(row, 2, rec["phone"], cell_fmt)
                worksheet.write(row, 3, rec["rooms"], cell_fmt)
                worksheet.write(row, 4, rec["check_in"], cell_fmt)
                worksheet.write(row, 5, rec["check_out"], cell_fmt)
                worksheet.write(row, 6, rec["adults"], cell_fmt)
                worksheet.write(row, 7, rec["children"], cell_fmt)
                worksheet.write(row, 8, rec["folio_name"], cell_fmt)
                worksheet.write(row, 9, rec["balance"], cell_num_fmt)
                row += 1

            row += 2
            # Departures
            worksheet.write(row, 0, _("EXPECTED DEPARTURES"), total_label_fmt)
            row += 1
            dep_headers = ["Res Ref", "Guest Name", "Phone", "Rooms", "Checkout Time", "Folio Ref", "Payment Status", "Balance"]
            for col, h in enumerate(dep_headers):
                worksheet.write(row, col, h, header_fmt)
            row += 1
            for rec in data["departures"]:
                worksheet.write(row, 0, rec["res_name"], cell_fmt)
                worksheet.write(row, 1, rec["guest"], cell_fmt)
                worksheet.write(row, 2, rec["phone"], cell_fmt)
                worksheet.write(row, 3, rec["rooms"], cell_fmt)
                worksheet.write(row, 4, rec["checkout_time"], cell_fmt)
                worksheet.write(row, 5, rec["folio_name"], cell_fmt)
                worksheet.write(row, 6, rec["payment_status"], cell_fmt)
                worksheet.write(row, 7, rec["balance"], cell_num_fmt)
                row += 1

        # Auto-adjust column widths
        worksheet.autofit()
        workbook.close()
        output.seek(0)
        file_bytes = output.read()

        file_name = f"Hotel_Report_{self.report_type}_{fields.Date.today()}.xlsx"
        attachment = self.env["ir.attachment"].create({
            "name": file_name,
            "type": "binary",
            "raw": file_bytes,
            "res_model": "hotel.report.wizard",
            "res_id": self.id,
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        })

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }
