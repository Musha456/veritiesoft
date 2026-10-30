from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class HotelGuestIdWizard(models.TransientModel):
    _name = "hotel.guest.id.wizard"
    _description = "Guest Identification Details"

    reservation_id = fields.Many2one(
        "hotel.reservation",
        string="Reservation",
        required=True,
        readonly=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Guest",
        required=True,
    )

    id_type = fields.Selection(
        [
            ("passport", "Passport"),
            ("national_id", "National ID"),
            ("driving_license", "Driving License"),
            ("other", "Other"),
        ],
        string="ID Type",
        default="national_id",
        required=True,
    )

    id_number = fields.Char(
        string="ID Number",
        required=True,
    )

    id_country_id = fields.Many2one(
        "res.country",
        string="Country / Nationality",
        required=True,
    )

    date_of_birth = fields.Date(
        string="Date of Birth",
    )

    gender = fields.Selection(
        [
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
        ],
        string="Gender",
    )

    def action_confirm_reservation(self):
        """Save guest identification details and confirm the reservation."""
        self.ensure_one()

        if not self.id_number:
            raise ValidationError(_("ID Number is required to proceed."))

        partner_vals = {
            "id_type": self.id_type,
            "id_number": self.id_number,
            "nationality": self.id_country_id.id if self.id_country_id else False,
        }
        if self.date_of_birth:
            partner_vals["date_of_birth"] = self.date_of_birth
        if self.gender:
            partner_vals["gender"] = self.gender

        self.partner_id.write(partner_vals)

        # Update reservation guest fields if present on the reservation model
        res_vals = {}
        if hasattr(self.reservation_id, "id_type"):
            res_vals["id_type"] = self.id_type
        if hasattr(self.reservation_id, "id_number"):
            res_vals["id_number"] = self.id_number
        if hasattr(self.reservation_id, "id_country_id") and self.id_country_id:
            res_vals["id_country_id"] = self.id_country_id.id
        if hasattr(self.reservation_id, "date_of_birth") and self.date_of_birth:
            res_vals["date_of_birth"] = self.date_of_birth
        if hasattr(self.reservation_id, "gender") and self.gender:
            res_vals["gender"] = self.gender

        if res_vals:
            self.reservation_id.write(res_vals)

        return self.reservation_id.with_context(skip_guest_id_check=True).action_confirm()
