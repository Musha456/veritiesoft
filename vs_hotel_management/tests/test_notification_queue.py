import datetime
from unittest.mock import patch, MagicMock
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'hotel_notification')
class TestHotelNotificationQueue(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env['res.partner'].create({
            'name': 'Notification Test Guest',
            'email': 'notification_guest@test.com',
            'phone': '+15551234567',
            'id_number': 'NOTIF12345',
        })

        cls.hotel = cls.env['hotel.hotel'].search([], limit=1)
        if not cls.hotel:
            cls.hotel = cls.env['hotel.hotel'].create({
                'name': 'Notification Test Hotel',
                'require_guest_identification': False,
            })

        cls.bed_type = cls.env['hotel.bed.type'].search([], limit=1)
        if not cls.bed_type:
            cls.bed_type = cls.env['hotel.bed.type'].create({'name': 'King Bed'})

        cls.category = cls.env['hotel.room.category'].create({
            'name': 'Notification Category',
            'bed_type_id': cls.bed_type.id,
            'max_adults': 2,
            'company_id': cls.env.company.id,
        })

        cls.building = cls.env['hotel.building'].search([('hotel_id', '=', cls.hotel.id)], limit=1)
        if not cls.building:
            cls.building = cls.env['hotel.building'].create({
                'name': 'Notif Building',
                'hotel_id': cls.hotel.id,
                'company_id': cls.env.company.id,
            })

        cls.floor = cls.env['hotel.building.floor'].search([('building_id', '=', cls.building.id)], limit=1)
        if not cls.floor:
            cls.floor = cls.env['hotel.building.floor'].create({
                'name': 'Floor 1',
                'building_id': cls.building.id,
            })

        cls.room = cls.env['hotel.room'].create({
            'room_number': 'N101',
            'room_category_id': cls.category.id,
            'hotel_id': cls.hotel.id,
            'building_id': cls.building.id,
            'floor_id': cls.floor.id,
            'status': 'available',
        })

        cls.rate_plan = cls.env['hotel.rate.plan'].create({
            'name': 'Notification Rate Plan',
            'hotel_id': cls.hotel.id,
            'room_category_ids': [(6, 0, [cls.category.id])],
            'state': 'active',
            'base_price': 100.0,
            'company_id': cls.env.company.id,
        })

        # Enable notification settings
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('vs_hotel_management.email_enabled', 'True')
        ICP.set_param('vs_hotel_management.whatsapp_enabled', 'True')
        ICP.set_param('vs_hotel_management.sms_enabled', 'True')
        ICP.set_param('vs_hotel_management.whatsapp_reservation_confirmed', 'True')
        ICP.set_param('vs_hotel_management.email_reservation_confirmed', 'True')
        ICP.set_param('vs_hotel_management.sms_reservation_confirmed', 'True')

    def test_01_action_confirm_queues_notifications_without_immediate_dispatch(self):
        """Verify that confirming a reservation queues WhatsApp and does not synchronously send."""
        check_in = datetime.datetime.now() + datetime.timedelta(days=1)
        check_out = check_in + datetime.timedelta(days=2)

        reservation = self.env['hotel.reservation'].create({
            'partner_id': self.partner.id,
            'hotel_id': self.hotel.id,
            'line_ids': [(0, 0, {
                'room_category_id': self.category.id,
                'rate_plan_id': self.rate_plan.id,
                'room_id': self.room.id,
                'check_in': check_in,
                'check_out': check_out,
                'room_price': 100.0,
            })],
        })

        # Patch requests.post so we verify no external HTTP calls are made during action_confirm
        with patch('requests.post') as mock_post:
            reservation.action_confirm()
            # Assert requests.post was NEVER called synchronously during button action
            mock_post.assert_not_called()

        self.assertEqual(reservation.state, 'confirmed')

        # Assert WhatsApp notification is created in queued status
        logs = self.env['hotel.whatsapp.log'].search([
            ('task_reference', '=', f'hotel.reservation,{reservation.id}'),
            ('event', '=', 'confirmed'),
        ])
        self.assertTrue(logs, "A WhatsApp log record should be created")
        self.assertEqual(logs[0].status, 'queued', "Status should be queued instead of sent or failed")

    def test_02_cron_process_whatsapp_queue(self):
        """Verify that cron_process_whatsapp_queue picks up queued logs and sends them."""
        # Create a queued log
        log = self.env['hotel.whatsapp.log'].create({
            'company_id': self.env.company.id,
            'recipient_id': self.partner.id,
            'phone_number': '15551234567',
            'task_type': 'reservation',
            'event': 'confirmed',
            'status': 'queued',
            'message': 'Test automated queue message',
        })

        # Configure dummy credentials on company
        self.env.company.write({
            'whatsapp_access_token': 'test_token',
            'whatsapp_phone_number_id': '1234567890',
            'whatsapp_api_version': 'v23.0',
        })

        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {'messages': [{'id': 'wamid.HBgLMTU1NTEyMzQ1Njc='}]}

        with patch('requests.post', return_value=mock_response) as mock_post:
            self.env['hotel.whatsapp.log'].cron_process_whatsapp_queue()
            mock_post.assert_called_once()

        log.invalidate_recordset()
        self.assertEqual(log.status, 'sent')
        self.assertEqual(log.meta_message_id, 'wamid.HBgLMTU1NTEyMzQ1Njc=')

    def test_03_cron_process_all_queues(self):
        """Verify unified cron executes without exception."""
        result = self.env['hotel.whatsapp.log'].cron_process_all_notification_queues()
        self.assertTrue(result)
