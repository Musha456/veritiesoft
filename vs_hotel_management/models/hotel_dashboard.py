# -*- coding: utf-8 -*-
from datetime import datetime, date, time, timedelta
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class HotelDashboard(models.AbstractModel):
    _name = "hotel.dashboard"
    _description = "Hotel Operations Dashboard Analytics Engine"

    @api.model
    def get_dashboard_data(self, hotel_id=None, date_from=None, date_to=None, preset="this_month"):
        """
        Main RPC Endpoint: Aggregates real-time hospitality KPIs, queues, and charts.
        """
        # 1. Determine Hotels
        Hotel = self.env["hotel.hotel"]
        all_hotels = Hotel.search([])
        hotels_data = [{"id": "all", "name": _("All Hotels")}] + [
            {"id": h.id, "name": h.name} for h in all_hotels
        ]

        if hotel_id and hotel_id != "all":
            try:
                selected_hotel_ids = [int(hotel_id)]
            except (ValueError, TypeError):
                selected_hotel_ids = all_hotels.ids
        else:
            selected_hotel_ids = all_hotels.ids

        # 2. Determine Dates
        today_date = fields.Date.context_today(self)
        now_dt = fields.Datetime.now()
        start_dt, end_dt = self._calculate_date_range(preset, today_date, date_from, date_to)

        # Base domains
        hotel_domain = [("hotel_id", "in", selected_hotel_ids)] if selected_hotel_ids else []

        # 3. Room & Operational Inventory
        Room = self.env["hotel.room"]
        room_domain = list(hotel_domain)
        total_rooms = Room.search_count(room_domain)
        operational_rooms = Room.search_count(room_domain + [("building_id.status", "in", ("operational", False))])
        total_operational_rooms = operational_rooms or total_rooms

        # Status counts
        available_rooms = Room.search_count(room_domain + [("status", "=", "available")])
        occupied_rooms = Room.search_count(room_domain + [("status", "=", "occupied")])
        reserved_rooms = Room.search_count(room_domain + [("status", "=", "reserved")])
        dirty_rooms = Room.search_count(room_domain + [("status", "=", "dirty")])
        cleaning_rooms = Room.search_count(room_domain + [("status", "=", "cleaning")])
        maintenance_rooms = Room.search_count(room_domain + [("status", "=", "maintenance")])
        out_of_order_rooms = Room.search_count(room_domain + [("status", "=", "out_of_order")])

        # Current Occupancy Rate
        occupancy_rate = 0.0
        if total_operational_rooms > 0:
            occupancy_rate = round((occupied_rooms / total_operational_rooms) * 100.0, 1)

        # 4. Front Desk Daily Queues (Today-specific)
        Reservation = self.env["hotel.reservation"]
        today_start_dt = datetime.combine(today_date, time.min)
        today_end_dt = datetime.combine(today_date, time.max)

        arrivals_today_domain = [
            ("check_in", ">=", today_start_dt),
            ("check_in", "<=", today_end_dt),
            ("state", "in", ("draft", "confirmed")),
        ] + hotel_domain
        arrivals_today_count = Reservation.search_count(arrivals_today_domain)

        departures_today_domain = [
            ("check_out", ">=", today_start_dt),
            ("check_out", "<=", today_end_dt),
            ("state", "=", "check_in"),
        ] + hotel_domain
        departures_today_count = Reservation.search_count(departures_today_domain)

        in_house_domain = [("state", "=", "check_in")] + hotel_domain
        in_house_count = Reservation.search_count(in_house_domain)

        overstay_domain = [
            ("state", "=", "check_in"),
            ("check_out", "<", now_dt),
        ] + hotel_domain
        overstay_count = Reservation.search_count(overstay_domain)

        # 5. Housekeeping & Maintenance Tasks
        Housekeeping = self.env["hotel.housekeeping"]
        active_housekeeping_count = Housekeeping.search_count(
            [("state", "not in", ("done", "cancelled"))] + hotel_domain
        )
        hk_inspection_count = Housekeeping.search_count(
            [("state", "=", "inspection")] + hotel_domain
        )

        Maintenance = self.env["hotel.maintenance"]
        active_maintenance_count = Maintenance.search_count(
            [("state", "not in", ("done", "cancelled"))] + hotel_domain
        )

        # 6. Financial Analytics & Hospitality Metrics (in selected date range)
        Folio = self.env["hotel.guest.folio"]
        FolioLine = self.env["hotel.guest.folio.line"]

        folio_line_domain = [
            ("date", ">=", start_dt),
            ("date", "<=", end_dt),
            ("folio_id.state", "!=", "cancelled"),
        ]
        if selected_hotel_ids:
            folio_line_domain.append(("folio_id.hotel_id", "in", selected_hotel_ids))

        # Total revenue in period
        all_folio_lines = FolioLine.search(folio_line_domain)
        total_revenue = sum(all_folio_lines.mapped("total_amount"))

        # Room revenue in period
        room_lines = all_folio_lines.filtered(lambda l: l.charge_type == "room")
        room_revenue = sum(room_lines.mapped("total_amount"))

        # Occupied room nights in period (from reservation lines)
        ResLine = self.env["hotel.reservation.line"]
        res_line_domain = [
            ("check_in", "<=", end_dt),
            ("check_out", ">=", start_dt),
            ("reservation_id.state", "in", ("confirmed", "check_in", "checked_out", "completed")),
        ]
        if selected_hotel_ids:
            res_line_domain.append(("hotel_id", "in", selected_hotel_ids))
        active_res_lines = ResLine.search(res_line_domain)

        occupied_nights = sum(active_res_lines.mapped("night_count")) or 1

        # Calculate ADR (Average Daily Rate)
        adr = round(room_revenue / occupied_nights, 2) if occupied_nights > 0 and room_revenue > 0 else 0.0

        # Calculate RevPAR
        days_in_period = max(1, (end_dt.date() - start_dt.date()).days + 1)
        available_room_nights = total_operational_rooms * days_in_period
        revpar = round(room_revenue / available_room_nights, 2) if available_room_nights > 0 and room_revenue > 0 else 0.0

        # Pending Folio Balance (uncollected from open/checked-in folios)
        open_folios = Folio.search([
            ("state", "in", ("draft", "open", "partially_paid")),
            ("balance_amount", ">", 0),
        ] + hotel_domain)
        pending_folio_balance = sum(open_folios.mapped("balance_amount"))

        # 7. Chart Visualizations Data
        # A. 7-Day Occupancy & Revenue Trend
        trend_data = self._get_seven_day_trend(today_date, selected_hotel_ids, total_operational_rooms)

        # B. Booking Sources Distribution
        booking_sources_data = self._get_booking_source_distribution(start_dt, end_dt, selected_hotel_ids)

        # C. Departmental Revenue Breakdown
        department_revenue_data = self._get_department_revenue_distribution(all_folio_lines)

        # D. Room Status Breakdown
        room_status_data = {
            "labels": [
                _("Available"),
                _("Occupied"),
                _("Reserved"),
                _("Dirty"),
                _("Cleaning"),
                _("Maintenance"),
                _("Out of Order"),
            ],
            "datasets": [{
                "data": [
                    available_rooms,
                    occupied_rooms,
                    reserved_rooms,
                    dirty_rooms,
                    cleaning_rooms,
                    maintenance_rooms,
                    out_of_order_rooms,
                ],
                "backgroundColor": [
                    "#10B981",  # green
                    "#3B82F6",  # blue
                    "#F59E0B",  # amber
                    "#EF4444",  # red
                    "#8B5CF6",  # purple
                    "#F97316",  # orange
                    "#6B7280",  # gray
                ],
            }]
        }

        # 8. Upcoming Live Feeds
        upcoming_arrivals = []
        arrivals_records = Reservation.search(
            [("state", "in", ("draft", "confirmed")), ("check_in", ">=", now_dt)] + hotel_domain,
            order="check_in asc",
            limit=5,
        )
        for arr in arrivals_records:
            rooms_str = ", ".join(arr.line_ids.mapped("room_id.room_number")) or _("Unassigned")
            upcoming_arrivals.append({
                "id": arr.id,
                "name": arr.name,
                "guest": arr.partner_id.name,
                "rooms": rooms_str,
                "check_in": arr.check_in.strftime("%d %b %Y, %H:%M") if arr.check_in else "",
                "state": dict(arr._fields["state"].selection).get(arr.state, arr.state),
            })

        upcoming_departures = []
        departures_records = Reservation.search(
            [("state", "=", "check_in"), ("check_out", ">=", today_start_dt)] + hotel_domain,
            order="check_out asc",
            limit=5,
        )
        for dep in departures_records:
            rooms_str = ", ".join(dep.line_ids.mapped("room_id.room_number")) or _("Unassigned")
            upcoming_departures.append({
                "id": dep.id,
                "name": dep.name,
                "guest": dep.partner_id.name,
                "rooms": rooms_str,
                "check_out": dep.check_out.strftime("%d %b %Y, %H:%M") if dep.check_out else "",
                "balance": f"{dep.folio_balance:,.2f}",
            })

        # Currency symbol
        currency = self.env.company.currency_id
        currency_symbol = currency.symbol or "$"

        return {
            "hotels": hotels_data,
            "selected_hotel_id": hotel_id or "all",
            "selected_preset": preset,
            "date_from": start_dt.strftime("%Y-%m-%d"),
            "date_to": end_dt.strftime("%Y-%m-%d"),
            "currency_symbol": currency_symbol,
            "kpis": {
                "occupancy_rate": occupancy_rate,
                "total_operational_rooms": total_operational_rooms,
                "occupied_rooms": occupied_rooms,
                "available_rooms": available_rooms,
                "total_revenue": f"{total_revenue:,.2f}",
                "room_revenue": f"{room_revenue:,.2f}",
                "adr": f"{adr:,.2f}",
                "revpar": f"{revpar:,.2f}",
                "pending_folio_balance": f"{pending_folio_balance:,.2f}",
            },
            "queues": {
                "arrivals_today": arrivals_today_count,
                "departures_today": departures_today_count,
                "in_house": in_house_count,
                "overstay": overstay_count,
            },
            "housekeeping": {
                "clean": available_rooms,
                "dirty": dirty_rooms,
                "cleaning": cleaning_rooms,
                "maintenance": maintenance_rooms,
                "out_of_order": out_of_order_rooms,
                "active_tasks": active_housekeeping_count,
                "inspections": hk_inspection_count,
                "active_maintenance": active_maintenance_count,
            },
            "charts": {
                "trend": trend_data,
                "sources": booking_sources_data,
                "departments": department_revenue_data,
                "room_status": room_status_data,
            },
            "upcoming_arrivals": upcoming_arrivals,
            "upcoming_departures": upcoming_departures,
        }

    def _calculate_date_range(self, preset, today, date_from=None, date_to=None):
        """Helper to compute start_dt and end_dt based on preset."""
        if preset == "today":
            start_date = today
            end_date = today
        elif preset == "yesterday":
            start_date = today - timedelta(days=1)
            end_date = start_date
        elif preset == "this_week":
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
        elif preset == "this_month":
            start_date = today.replace(day=1)
            end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)
        elif preset == "last_30_days":
            start_date = today - timedelta(days=29)
            end_date = today
        elif preset == "this_year":
            start_date = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
        elif preset == "custom" and date_from and date_to:
            try:
                start_date = fields.Date.from_string(date_from)
                end_date = fields.Date.from_string(date_to)
            except Exception:
                start_date = today.replace(day=1)
                end_date = today
        else:
            start_date = today.replace(day=1)
            end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)

        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)
        return start_dt, end_dt

    def _get_seven_day_trend(self, today, selected_hotel_ids, total_rooms):
        """Computes daily occupancy count and revenue for the last 7 days."""
        labels = []
        occupancy_points = []
        revenue_points = []

        FolioLine = self.env["hotel.guest.folio.line"]
        ResLine = self.env["hotel.reservation.line"]

        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_start = datetime.combine(day, time.min)
            day_end = datetime.combine(day, time.max)
            labels.append(day.strftime("%a (%d %b)"))

            # Active occupied reservations on this day
            res_domain = [
                ("check_in", "<=", day_end),
                ("check_out", ">=", day_start),
                ("reservation_id.state", "in", ("confirmed", "check_in", "checked_out", "completed")),
            ]
            if selected_hotel_ids:
                res_domain.append(("hotel_id", "in", selected_hotel_ids))
            occupied_count = ResLine.search_count(res_domain)
            occupancy_points.append(occupied_count)

            # Revenue on this day
            f_domain = [
                ("date", ">=", day_start),
                ("date", "<=", day_end),
                ("folio_id.state", "!=", "cancelled"),
            ]
            if selected_hotel_ids:
                f_domain.append(("folio_id.hotel_id", "in", selected_hotel_ids))
            day_rev = sum(FolioLine.search(f_domain).mapped("total_amount"))
            revenue_points.append(round(day_rev, 2))

        return {
            "labels": labels,
            "datasets": [
                {
                    "label": _("Occupied Rooms"),
                    "type": "bar",
                    "data": occupancy_points,
                    "backgroundColor": "#3B82F6",
                    "borderRadius": 6,
                    "yAxisID": "y",
                },
                {
                    "label": _("Revenue"),
                    "type": "line",
                    "data": revenue_points,
                    "borderColor": "#10B981",
                    "backgroundColor": "rgba(16, 185, 129, 0.15)",
                    "borderWidth": 3,
                    "fill": True,
                    "tension": 0.35,
                    "yAxisID": "y1",
                },
            ]
        }

    def _get_booking_source_distribution(self, start_dt, end_dt, selected_hotel_ids):
        """Groups reservations by booking source."""
        Reservation = self.env["hotel.reservation"]
        domain = [("create_date", ">=", start_dt), ("create_date", "<=", end_dt)]
        if selected_hotel_ids:
            domain.append(("hotel_id", "in", selected_hotel_ids))

        reservations = Reservation.search(domain)
        source_counts = {}
        for r in reservations:
            source_label = dict(r._fields["booking_source"].selection).get(r.booking_source, r.booking_source)
            source_counts[source_label] = source_counts.get(source_label, 0) + 1

        if not source_counts:
            source_counts = {_("Direct / Walk-in"): 1}

        palette = ["#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899", "#6366F1", "#14B8A6"]
        return {
            "labels": list(source_counts.keys()),
            "datasets": [{
                "data": list(source_counts.values()),
                "backgroundColor": palette[:len(source_counts)],
            }]
        }

    def _get_department_revenue_distribution(self, folio_lines):
        """Groups revenue by charge type."""
        dept_amounts = {}
        type_labels = dict(self.env["hotel.guest.folio.line"]._fields["charge_type"].selection)

        for line in folio_lines:
            c_type = line.charge_type
            label = type_labels.get(c_type, c_type.capitalize())
            dept_amounts[label] = dept_amounts.get(label, 0.0) + line.total_amount

        if not dept_amounts:
            dept_amounts = {_("Room"): 0.0}

        sorted_items = sorted(dept_amounts.items(), key=lambda x: x[1], reverse=True)[:6]
        labels = [item[0] for item in sorted_items]
        values = [round(item[1], 2) for item in sorted_items]

        return {
            "labels": labels,
            "datasets": [{
                "label": _("Revenue"),
                "data": values,
                "backgroundColor": [
                    "#3B82F6",
                    "#10B981",
                    "#F59E0B",
                    "#8B5CF6",
                    "#EC4899",
                    "#14B8A6",
                ][:len(labels)],
                "borderRadius": 6,
            }]
        }
