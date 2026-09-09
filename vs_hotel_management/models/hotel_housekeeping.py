from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class HotelHousekeeping(models.Model):
    _name = "hotel.housekeeping"
    _description = "Hotel Housekeeping"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, scheduled_date asc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default="/",
    )

    room_id = fields.Many2one(
        "hotel.room",
        string="Room",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )

    room_category_id = fields.Many2one(
        related="room_id.room_category_id",
        string="Room Category",
        store=True,
        readonly=True,
    )

    reservation_id = fields.Many2one(
    "hotel.reservation",
    string="Reservation",
    ondelete="restrict",
    index=True,
    )

    room_booking_id = fields.Many2one(
        "hotel.room.booking",
        string="Room Booking",
        ondelete="restrict",
        index=True,
    )

    housekeeping_type = fields.Selection(
        [
            ("checkout", "Checkout Cleaning"),
            ("stayover", "Stayover Cleaning"),
            ("deep", "Deep Cleaning"),
            ("maintenance", "Maintenance"),
        ],
        string="Type",
        required=True,
        default="checkout",
        tracking=True,
    )

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        required=True,
        default="pending",
        tracking=True,
        copy=False,
    )

    priority = fields.Selection(
        [
            ("0", "Normal"),
            ("1", "High"),
        ],
        string="Priority",
        default="0",
        index=True,
    )

    scheduled_date = fields.Datetime(
        string="Scheduled Date",
        default=fields.Datetime.now,
        required=True,
        index=True,
    )

    started_at = fields.Datetime(
        string="Started At",
        readonly=True,
    )

    completed_at = fields.Datetime(
        string="Completed At",
        readonly=True,
    )

    assigned_to = fields.Many2one(
        "res.users",
        string="Assigned To",
        tracking=True,
    )

    notes = fields.Text(
        string="Notes",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    assigned_to_domain = fields.Many2many(
        "res.users",
        compute="_compute_assigned_to_domain",
    )

    @api.depends()
    def _compute_assigned_to_domain(self):
        group = self.env.ref(
            "vs_hotel_management.group_hotel_housekeeping_user",
            raise_if_not_found=False,
        )

        users = group.users.filtered(lambda u: u.active) if group else self.env["res.users"]

        for record in self:
            record.assigned_to_domain = users

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "hotel.housekeeping"
                ) or "/"

        return super().create(vals_list)

    def _find_active_task(self, room):
        return self.search(
            [
                ("room_id", "=", room.id),
                ("state", "in", ("pending", "in_progress")),
            ],
            limit=1,
        )

    @api.model
    def create_checkout_task(
            self,
            room,
            reservation=None,
            room_booking=None,
    ):
        existing = self._find_active_task(room)

        if existing:
            return existing

        return self.create({
            "room_id": room.id,
            "reservation_id": reservation.id if reservation else False,
            "room_booking_id": (
                room_booking.id if room_booking else False
            ),
            "housekeeping_type": "checkout",
            "state": "pending",
            "scheduled_date": fields.Datetime.now(),
        })

    def action_start(self):
        for task in self:
            if task.state != "pending":
                raise UserError(
                    _("Only pending housekeeping tasks can be started.")
                )

            if not task.assigned_to:
                raise UserError(
                    _(
                        "Please assign housekeeping task %s "
                        "to a user before starting."
                    )
                    % task.display_name
                )

            task.write({
                "state": "in_progress",
                "started_at": fields.Datetime.now(),
            })

        return True

    def action_done(self):
        for task in self:

            if task.state != "in_progress":
                raise UserError(
                    _(
                        "Only housekeeping tasks in progress "
                        "can be completed."
                    )
                )

            task.write({
                "state": "done",
                "completed_at": fields.Datetime.now(),
            })

            if task.room_id.status == "cleaning":
                task.room_id.status = "available"

    def action_cancel(self):
        for task in self:

            if task.state == "done":
                raise UserError(
                    _(
                        "Completed housekeeping tasks "
                        "cannot be cancelled."
                    )
                )

            task.state = "cancelled"

            task.room_id.write({
                "status": "dirty",
            })

    def action_assign_task(self):
        self.ensure_one()

        if self.state not in ("pending", "in_progress"):
            raise UserError(
                _("Only pending or in-progress tasks can be assigned.")
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Assign Housekeeping"),
            "res_model": "hotel.task.assignment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_task_type": "housekeeping",
                "default_room_id": self.room_id.id,
                "default_housekeeping_id": self.id,
            },
        }