
from odoo import fields, models


class HotelWhatsAppLog(models.Model):
    _name = "hotel.whatsapp.log"
    _description = "Hotel WhatsApp Notification Log"
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        readonly=True,
        default="New",
        copy=False,
    )
    recipient_id = fields.Many2one(
        "res.partner",
        string="Recipient",
        readonly=True,
        index=True,
    )
    phone_number = fields.Char(
        string="WhatsApp Number",
        readonly=True,
        index=True,
    )
    task_type = fields.Selection(
        [
            ("housekeeping", "Housekeeping"),
            ("maintenance", "Maintenance"),
        ],
        required=True,
        readonly=True,
        index=True,
    )
    event = fields.Selection(
        [
            ("assigned", "Assigned"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        readonly=True,
    )
    task_reference = fields.Reference(
        selection=[
            ("hotel.housekeeping", "Housekeeping Task"),
            ("hotel.maintenance", "Maintenance Task"),
        ],
        string="Task",
        readonly=True,
        index=True,
    )
    message = fields.Text(string="Message Details", readonly=True)
    status = fields.Selection(
        [
            ("queued", "Queued"),
            ("sent", "Accepted by Meta"),
            ("delivered", "Delivered"),
            ("read", "Read"),
            ("failed", "Failed"),
        ],
        string="Status",
        required=True,
        default="queued",
        readonly=True,
        index=True,
    )
    meta_message_id = fields.Char(
        string="Meta Message ID",
        readonly=True,
        index=True,
    )
    error_details = fields.Text(string="Error Details", readonly=True)
    sent_at = fields.Datetime(string="Accepted At", readonly=True)
    delivered_at = fields.Datetime(string="Delivered At", readonly=True)
    read_at = fields.Datetime(string="Read At", readonly=True)

    def init(self):
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS hotel_whatsapp_log_meta_message_id_idx
            ON hotel_whatsapp_log (meta_message_id)
        """)
