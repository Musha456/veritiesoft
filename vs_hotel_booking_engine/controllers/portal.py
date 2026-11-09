# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class HotelCustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        if "reservation_count" in counters:
            values["reservation_count"] = request.env["hotel.reservation"].search_count([
                ("partner_id", "=", partner.id)
            ]) if not request.env.user._is_public() else 0
        return values

    @http.route(["/my/reservations", "/my/reservations/page/<int:page>"], type="http", auth="user", website=True)
    def portal_my_reservations(self, page=1, sortby=None, filterby=None, **kwargs):
        """Portal Page: Lists all reservations for the logged-in guest."""
        partner = request.env.user.partner_id
        Reservation = request.env["hotel.reservation"]

        domain = [("partner_id", "=", partner.id)]

        if filterby:
            if filterby == "active":
                domain.append(("state", "in", ("draft", "confirmed", "check_in")))
            elif filterby == "completed":
                domain.append(("state", "in", ("checked_out", "completed")))
            elif filterby == "cancelled":
                domain.append(("state", "=", "cancelled"))

        reservation_count = Reservation.search_count(domain)
        pager = portal_pager(
            url="/my/reservations",
            total=reservation_count,
            page=page,
            step=10,
        )

        reservations = Reservation.search(domain, order="create_date desc, id desc", limit=10, offset=pager["offset"])

        values = self._prepare_portal_layout_values()
        values.update({
            "reservations": reservations,
            "page_name": "hotel_reservations",
            "pager": pager,
            "default_url": "/my/reservations",
            "filterby": filterby or "all",
        })
        return request.render("vs_hotel_booking_engine.portal_my_reservations", values)

    @http.route("/my/reservation/<int:res_id>", type="http", auth="user", website=True)
    def portal_my_reservation_detail(self, res_id, **kwargs):
        """Portal Page: Detailed view of a guest reservation."""
        partner = request.env.user.partner_id
        reservation = request.env["hotel.reservation"].browse(res_id)

        if not reservation.exists() or reservation.partner_id.id != partner.id:
            return request.redirect("/my/reservations")

        hotel = reservation.hotel_id

        # Check if room switching is allowed
        company = hotel.company_id or request.env.company
        allow_switch = getattr(company, "allow_guest_room_change", True) and reservation.state in ("draft", "confirmed")

        switchable_lines = []
        if allow_switch:
            for line in reservation.line_ids:
                available_rooms = reservation.get_available_switch_rooms(line.id)
                switchable_lines.append({
                    "line": line,
                    "available_rooms": available_rooms,
                })

        values = self._prepare_portal_layout_values()
        values.update({
            "reservation": reservation,
            "hotel": hotel,
            "theme_style": hotel.theme_style,
            "allow_switch": allow_switch,
            "allow_cancel": reservation.state in ("draft", "confirmed"),
            "switchable_lines": switchable_lines,
            "page_name": "hotel_reservation_detail",
            "success_message": kwargs.get("success_message"),
            "error_message": kwargs.get("error_message"),
        })
        return request.render("vs_hotel_booking_engine.portal_my_reservation_detail", values)

    @http.route("/my/reservation/<int:res_id>/switch_room", type="http", auth="user", methods=["POST"], website=True)
    def portal_switch_room(self, res_id, line_id, new_room_id, **kwargs):
        """Portal Action: Changes room before check-in."""
        partner = request.env.user.partner_id
        reservation = request.env["hotel.reservation"].browse(res_id)

        if not reservation.exists() or reservation.partner_id.id != partner.id:
            return request.redirect("/my/reservations")

        try:
            reservation.action_switch_line_room(int(line_id), int(new_room_id))
            return request.redirect(f"/my/reservation/{res_id}?success_message=Room+changed+successfully!")
        except Exception as e:
            return request.redirect(f"/my/reservation/{res_id}?error_message={str(e)}")

    @http.route("/my/reservation/<int:res_id>/cancel", type="http", auth="user", methods=["POST"], website=True)
    def portal_cancel_reservation(self, res_id, **kwargs):
        """Portal Action: Allows guest to cancel reservation before check-in."""
        partner = request.env.user.partner_id
        reservation = request.env["hotel.reservation"].browse(res_id)

        if not reservation.exists() or reservation.partner_id.id != partner.id:
            return request.redirect("/my/reservations")

        reason = kwargs.get("cancel_reason", "Cancelled by guest via portal.")
        try:
            reservation.action_portal_cancel(reason=reason)
            return request.redirect(f"/my/reservation/{res_id}?success_message=Reservation+cancelled+successfully.")
        except Exception as e:
            return request.redirect(f"/my/reservation/{res_id}?error_message={str(e)}")

    @http.route("/my/reservation/<int:res_id>/voucher", type="http", auth="user", website=True)
    def portal_download_voucher(self, res_id, **kwargs):
        """Portal Action: Generates and downloads PDF Reservation Voucher."""
        partner = request.env.user.partner_id
        reservation = request.env["hotel.reservation"].browse(res_id)

        if not reservation.exists() or reservation.partner_id.id != partner.id:
            return request.redirect("/my/reservations")

        pdf_content, _ = request.env["ir.actions.report"].sudo()._render_qweb_pdf(
            "vs_hotel_management.action_report_hotel_reservation",
            [reservation.id]
        )
        pdfhttpheaders = [
            ("Content-Type", "application/pdf"),
            ("Content-Length", len(pdf_content)),
            ("Content-Disposition", f"attachment; filename=Reservation_{reservation.name}.pdf"),
        ]
        return request.make_response(pdf_content, headers=pdfhttpheaders)
