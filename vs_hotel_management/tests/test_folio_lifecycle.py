import datetime
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install', 'hotel_folio_lifecycle')
class TestHotelFolioLifecycle(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env['res.partner'].create({
            'name': 'Folio Lifecycle Guest',
            'is_hotel_guest': True,
            'email': 'folio_guest@test.com',
            'id_number': 'FOLIO12345',
        })

        cls.hotel = cls.env['hotel.hotel'].search([], limit=1)
        if not cls.hotel:
            cls.hotel = cls.env['hotel.hotel'].create({
                'name': 'Folio Test Hotel',
                'require_guest_identification': False,
            })

        cls.bed_type = cls.env['hotel.bed.type'].search([], limit=1)
        if not cls.bed_type:
            cls.bed_type = cls.env['hotel.bed.type'].create({'name': 'King Bed'})

        cls.category = cls.env['hotel.room.category'].create({
            'name': 'Folio Test Category',
            'bed_type_id': cls.bed_type.id,
            'max_adults': 2,
            'company_id': cls.env.company.id,
        })

        cls.building = cls.env['hotel.building'].search([('hotel_id', '=', cls.hotel.id)], limit=1)
        if not cls.building:
            cls.building = cls.env['hotel.building'].create({
                'name': 'Folio Building',
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
            'room_number': 'F101',
            'room_category_id': cls.category.id,
            'hotel_id': cls.hotel.id,
            'building_id': cls.building.id,
            'floor_id': cls.floor.id,
            'status': 'available',
        })

        cls.rate_plan = cls.env['hotel.rate.plan'].create({
            'name': 'Folio Rate Plan',
            'hotel_id': cls.hotel.id,
            'room_category_ids': [(6, 0, [cls.category.id])],
            'state': 'active',
            'base_price': 200.0,
            'company_id': cls.env.company.id,
        })

    def _create_and_checkout_reservation(self):
        """Helper to create, confirm, reserve, check-in and check-out a reservation."""
        check_in = datetime.datetime.now() - datetime.timedelta(days=2)
        check_out = datetime.datetime.now() - datetime.timedelta(hours=1)

        reservation = self.env['hotel.reservation'].create({
            'partner_id': self.partner.id,
            'hotel_id': self.hotel.id,
            'line_ids': [(0, 0, {
                'room_category_id': self.category.id,
                'rate_plan_id': self.rate_plan.id,
                'room_id': self.room.id,
                'check_in': check_in,
                'check_out': check_out,
                'room_price': 200.0,
            })],
        })

        reservation.action_confirm()
        reservation.action_reserve()
        reservation.action_check_in()
        reservation.action_check_out()

        folio = reservation.folio_ids.filtered(lambda f: f.state != 'cancelled')[:1]
        self.assertTrue(folio, "A guest folio must exist after check-in/out")
        return reservation, folio

    def test_01_partial_payment_sets_partially_paid(self):
        """Verify folio state is 'partially_paid' when partial payment is made and balance != 0."""
        reservation, folio = self._create_and_checkout_reservation()

        self.assertGreater(folio.total_amount, 0)
        total = folio.total_amount
        partial_amount = total / 2.0

        # Add partial payment line
        self.env['hotel.guest.folio.line'].create({
            'folio_id': folio.id,
            'description': 'Partial Deposit Payment',
            'charge_type': 'payment',
            'unit_price': partial_amount,
            'quantity': 1.0,
        })

        folio.invalidate_recordset()
        self.assertAlmostEqual(folio.paid_amount, partial_amount)
        self.assertGreater(folio.balance_amount, 0.001)
        self.assertEqual(folio.state, 'partially_paid', "Folio should transition to 'partially_paid' when balance remains")

    def test_02_full_payment_sets_paid_automatically(self):
        """Verify folio state is automatically 'paid' when payment equals total and balance is zero."""
        reservation, folio = self._create_and_checkout_reservation()

        total = folio.total_amount
        # Add full payment line
        self.env['hotel.guest.folio.line'].create({
            'folio_id': folio.id,
            'description': 'Full Settlement',
            'charge_type': 'payment',
            'unit_price': total,
            'quantity': 1.0,
        })

        folio.invalidate_recordset()
        self.assertAlmostEqual(folio.balance_amount, 0.0)
        self.assertEqual(folio.state, 'paid', "Folio should automatically be 'paid' when balance is zero")

    def test_03_reservation_complete_validates_paid_and_closes_folio(self):
        """
        Verify that action_complete blocks if folio is not in 'paid',
        and when folio is in 'paid', it transitions folio to 'closed' and reservation to 'completed'.
        """
        reservation, folio = self._create_and_checkout_reservation()

        # Step A: Partial payment -> attempt complete -> must raise UserError
        self.env['hotel.guest.folio.line'].create({
            'folio_id': folio.id,
            'description': 'Partial Payment',
            'charge_type': 'payment',
            'unit_price': 100.0,
            'quantity': 1.0,
        })

        folio.invalidate_recordset()
        self.assertEqual(folio.state, 'partially_paid')

        with self.assertRaises(UserError):
            reservation.action_complete()

        self.assertEqual(reservation.state, 'checked_out', "Reservation state must remain checked_out when folio is unpaid")

        # Step B: Settle the remaining balance
        remaining_balance = folio.balance_amount
        self.env['hotel.guest.folio.line'].create({
            'folio_id': folio.id,
            'description': 'Final Payment',
            'charge_type': 'payment',
            'unit_price': remaining_balance,
            'quantity': 1.0,
        })

        folio.invalidate_recordset()
        self.assertEqual(folio.state, 'paid', "Folio should be in 'paid' status after full settlement")

        # Step C: Complete reservation -> must succeed, close folio, and mark reservation completed
        reservation.action_complete()

        folio.invalidate_recordset()
        self.assertEqual(folio.state, 'closed', "Folio state must transition to 'closed' upon completing reservation")
        self.assertEqual(reservation.state, 'completed', "Reservation state must transition to 'completed'")
