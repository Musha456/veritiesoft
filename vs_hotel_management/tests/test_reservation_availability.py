import datetime
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError


@tagged('post_install', '-at_install', 'hotel_availability')
class TestHotelReservationAvailability(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Guest',
            'email': 'guest@test.com',
            'id_number': 'ID12345678',
        })

        cls.hotel = cls.env['hotel.hotel'].search([], limit=1)
        if not cls.hotel:
            cls.hotel = cls.env['hotel.hotel'].create({
                'name': 'Test Hotel',
                'require_guest_identification': False,
            })

        cls.bed_type = cls.env['hotel.bed.type'].search([], limit=1)
        if not cls.bed_type:
            cls.bed_type = cls.env['hotel.bed.type'].create({'name': 'King Bed'})

        cls.category_deluxe = cls.env['hotel.room.category'].create({
            'name': 'Deluxe Test Category',
            'bed_type_id': cls.bed_type.id,
            'max_adults': 2,
            'max_children': 1,
            'company_id': cls.env.company.id,
        })

        cls.category_standard = cls.env['hotel.room.category'].create({
            'name': 'Standard Test Category',
            'bed_type_id': cls.bed_type.id,
            'max_adults': 2,
            'max_children': 0,
            'company_id': cls.env.company.id,
        })

        cls.building = cls.env['hotel.building'].search([('hotel_id', '=', cls.hotel.id)], limit=1)
        if not cls.building:
            cls.building = cls.env['hotel.building'].create({
                'name': 'Main Building',
                'hotel_id': cls.hotel.id,
                'company_id': cls.env.company.id,
            })

        cls.floor = cls.env['hotel.building.floor'].search([('building_id', '=', cls.building.id)], limit=1)
        if not cls.floor:
            cls.floor = cls.env['hotel.building.floor'].create({
                'name': 'Floor 1',
                'building_id': cls.building.id,
            })

        cls.rate_plan = cls.env['hotel.rate.plan'].create({
            'name': 'Test Best Available Rate',
            'hotel_id': cls.hotel.id,
            'room_category_ids': [(6, 0, [cls.category_deluxe.id, cls.category_standard.id])],
            'state': 'active',
            'base_price': 100.0,
            'company_id': cls.env.company.id,
        })

        cls.room_101 = cls.env['hotel.room'].create({
            'room_number': 'TEST-101',
            'code': 'TEST-101',
            'room_category_id': cls.category_deluxe.id,
            'building_id': cls.building.id,
            'floor_id': cls.floor.id,
            'status': 'available',
            'company_id': cls.env.company.id,
        })

        cls.room_102 = cls.env['hotel.room'].create({
            'room_number': 'TEST-102',
            'code': 'TEST-102',
            'room_category_id': cls.category_deluxe.id,
            'building_id': cls.building.id,
            'floor_id': cls.floor.id,
            'status': 'available',
            'company_id': cls.env.company.id,
        })

        cls.room_standard = cls.env['hotel.room'].create({
            'room_number': 'TEST-201',
            'code': 'TEST-201',
            'room_category_id': cls.category_standard.id,
            'building_id': cls.building.id,
            'floor_id': cls.floor.id,
            'status': 'available',
            'company_id': cls.env.company.id,
        })

    def _create_reservation(self, check_in, check_out, room, category=None, state='draft', adults=1, children=0):
        if category is None:
            category = room.room_category_id

        reservation = self.env['hotel.reservation'].create({
            'partner_id': self.partner.id,
            'hotel_id': self.hotel.id,
            'check_in': check_in,
            'check_out': check_out,
            'line_ids': [
                (0, 0, {
                    'room_id': room.id,
                    'room_category_id': category.id,
                    'rate_plan_id': self.rate_plan.id,
                    'check_in': check_in,
                    'check_out': check_out,
                    'adults': adults,
                    'children': children,
                })
            ]
        })
        if state in ('confirmed', 'reserved', 'checked_in'):
            reservation.action_confirm()
            if state in ('reserved', 'checked_in'):
                reservation.action_reserve()
                if state == 'checked_in':
                    reservation.action_check_in()
        elif state == 'cancelled':
            reservation.action_confirm()
            reservation.sudo().action_cancel()
        return reservation

    # -------------------------------------------------------------------------
    # Test 1 — Exact overlap
    # Existing: 10 Oct -> 15 Oct. New: 10 Oct -> 15 Oct. Expected: REJECT
    # -------------------------------------------------------------------------
    def test_01_exact_overlap(self):
        in_date = datetime.datetime(2026, 10, 10, 14, 0)
        out_date = datetime.datetime(2026, 10, 15, 11, 0)

        # Existing confirmed reservation
        self._create_reservation(in_date, out_date, self.room_101, state='confirmed')

        # New reservation with exact same dates and room
        res2 = self._create_reservation(in_date, out_date, self.room_101, state='draft')
        with self.assertRaises(ValidationError):
            res2.action_confirm()

    # -------------------------------------------------------------------------
    # Test 2 — Partial overlap from beginning
    # Existing: 10 Oct -> 15 Oct. New: 8 Oct -> 12 Oct. Expected: REJECT
    # -------------------------------------------------------------------------
    def test_02_partial_overlap_from_beginning(self):
        self._create_reservation(
            datetime.datetime(2026, 10, 10, 14, 0),
            datetime.datetime(2026, 10, 15, 11, 0),
            self.room_101,
            state='confirmed',
        )

        res2 = self._create_reservation(
            datetime.datetime(2026, 10, 8, 14, 0),
            datetime.datetime(2026, 10, 12, 11, 0),
            self.room_101,
            state='draft',
        )
        with self.assertRaises(ValidationError):
            res2.action_confirm()

    # -------------------------------------------------------------------------
    # Test 3 — Partial overlap from end
    # Existing: 10 Oct -> 15 Oct. New: 13 Oct -> 18 Oct. Expected: REJECT
    # -------------------------------------------------------------------------
    def test_03_partial_overlap_from_end(self):
        self._create_reservation(
            datetime.datetime(2026, 10, 10, 14, 0),
            datetime.datetime(2026, 10, 15, 11, 0),
            self.room_101,
            state='confirmed',
        )

        res2 = self._create_reservation(
            datetime.datetime(2026, 10, 13, 14, 0),
            datetime.datetime(2026, 10, 18, 11, 0),
            self.room_101,
            state='draft',
        )
        with self.assertRaises(ValidationError):
            res2.action_confirm()

    # -------------------------------------------------------------------------
    # Test 4 — New reservation completely inside existing
    # Existing: 10 Oct -> 20 Oct. New: 12 Oct -> 15 Oct. Expected: REJECT
    # -------------------------------------------------------------------------
    def test_04_new_completely_inside_existing(self):
        self._create_reservation(
            datetime.datetime(2026, 10, 10, 14, 0),
            datetime.datetime(2026, 10, 20, 11, 0),
            self.room_101,
            state='confirmed',
        )

        res2 = self._create_reservation(
            datetime.datetime(2026, 10, 12, 14, 0),
            datetime.datetime(2026, 10, 15, 11, 0),
            self.room_101,
            state='draft',
        )
        with self.assertRaises(ValidationError):
            res2.action_confirm()

    # -------------------------------------------------------------------------
    # Test 5 — Existing reservation completely inside new
    # Existing: 12 Oct -> 15 Oct. New: 10 Oct -> 20 Oct. Expected: REJECT
    # -------------------------------------------------------------------------
    def test_05_existing_completely_inside_new(self):
        self._create_reservation(
            datetime.datetime(2026, 10, 12, 14, 0),
            datetime.datetime(2026, 10, 15, 11, 0),
            self.room_101,
            state='confirmed',
        )

        res2 = self._create_reservation(
            datetime.datetime(2026, 10, 10, 14, 0),
            datetime.datetime(2026, 10, 20, 11, 0),
            self.room_101,
            state='draft',
        )
        with self.assertRaises(ValidationError):
            res2.action_confirm()

    # -------------------------------------------------------------------------
    # Test 6 — Back-to-back booking
    # Existing: 10 Oct -> 15 Oct. New: 15 Oct -> 20 Oct. Expected: ALLOW
    # -------------------------------------------------------------------------
    def test_06_back_to_back_booking(self):
        self._create_reservation(
            datetime.datetime(2026, 10, 10, 14, 0),
            datetime.datetime(2026, 10, 15, 11, 0),
            self.room_101,
            state='confirmed',
        )

        res2 = self._create_reservation(
            datetime.datetime(2026, 10, 15, 14, 0),
            datetime.datetime(2026, 10, 20, 11, 0),
            self.room_101,
            state='draft',
        )
        # Must confirm without error
        res2.action_confirm()
        self.assertEqual(res2.state, 'confirmed')

    # -------------------------------------------------------------------------
    # Test 7 — Before existing booking
    # Existing: 10 Oct -> 15 Oct. New: 5 Oct -> 10 Oct. Expected: ALLOW
    # -------------------------------------------------------------------------
    def test_07_before_existing_booking(self):
        self._create_reservation(
            datetime.datetime(2026, 10, 10, 14, 0),
            datetime.datetime(2026, 10, 15, 11, 0),
            self.room_101,
            state='confirmed',
        )

        res2 = self._create_reservation(
            datetime.datetime(2026, 10, 5, 14, 0),
            datetime.datetime(2026, 10, 10, 11, 0),
            self.room_101,
            state='draft',
        )
        res2.action_confirm()
        self.assertEqual(res2.state, 'confirmed')

    # -------------------------------------------------------------------------
    # Test 8 — After existing booking
    # Existing: 10 Oct -> 15 Oct. New: 15 Oct -> 20 Oct. Expected: ALLOW
    # -------------------------------------------------------------------------
    def test_08_after_existing_booking(self):
        self._create_reservation(
            datetime.datetime(2026, 10, 10, 14, 0),
            datetime.datetime(2026, 10, 15, 11, 0),
            self.room_101,
            state='confirmed',
        )

        res2 = self._create_reservation(
            datetime.datetime(2026, 10, 15, 14, 0),
            datetime.datetime(2026, 10, 20, 11, 0),
            self.room_101,
            state='draft',
        )
        res2.action_confirm()
        self.assertEqual(res2.state, 'confirmed')

    # -------------------------------------------------------------------------
    # Test 9 — Cancelled reservation
    # Existing cancelled: 10 Oct -> 15 Oct. New: 10 Oct -> 15 Oct. Expected: ALLOW
    # -------------------------------------------------------------------------
    def test_09_cancelled_reservation(self):
        self._create_reservation(
            datetime.datetime(2026, 10, 10, 14, 0),
            datetime.datetime(2026, 10, 15, 11, 0),
            self.room_101,
            state='cancelled',
        )

        res2 = self._create_reservation(
            datetime.datetime(2026, 10, 10, 14, 0),
            datetime.datetime(2026, 10, 15, 11, 0),
            self.room_101,
            state='draft',
        )
        res2.action_confirm()
        self.assertEqual(res2.state, 'confirmed')

    # -------------------------------------------------------------------------
    # Test 10 — Editing current reservation
    # Existing: 10 Oct -> 15 Oct. Edit same reservation. Expected: ALLOW
    # -------------------------------------------------------------------------
    def test_10_editing_current_reservation(self):
        res = self._create_reservation(
            datetime.datetime(2026, 10, 10, 14, 0),
            datetime.datetime(2026, 10, 15, 11, 0),
            self.room_101,
            state='confirmed',
        )

        # Editing notes or saving the same reservation must not trigger a false overlap
        res.write({'internal_notes': 'Guest requested upper floor'})
        res.line_ids.write({'adults': 2})
        self.assertEqual(res.state, 'confirmed')

    # -------------------------------------------------------------------------
    # Test 11 — Maintenance
    # Room 101: Maintenance. New reservation: 10 Oct -> 15 Oct. Expected: REJECT
    # -------------------------------------------------------------------------
    def test_11_maintenance_room(self):
        self.room_101.write({'status': 'maintenance'})

        # Attempting to assign room in maintenance must be rejected
        with self.assertRaises(ValidationError):
            self._create_reservation(
                datetime.datetime(2026, 10, 10, 14, 0),
                datetime.datetime(2026, 10, 15, 11, 0),
                self.room_101,
                state='draft',
            )

        # Reset status back to available
        self.room_101.write({'status': 'available'})

    # -------------------------------------------------------------------------
    # Test 12 — Different rooms
    # Room 101 booked, Room 102 booked for same dates. Expected: ALLOW
    # -------------------------------------------------------------------------
    def test_12_different_rooms(self):
        self._create_reservation(
            datetime.datetime(2026, 10, 10, 14, 0),
            datetime.datetime(2026, 10, 15, 11, 0),
            self.room_101,
            state='confirmed',
        )

        res2 = self._create_reservation(
            datetime.datetime(2026, 10, 10, 14, 0),
            datetime.datetime(2026, 10, 15, 11, 0),
            self.room_102,
            state='draft',
        )
        res2.action_confirm()
        self.assertEqual(res2.state, 'confirmed')

    # -------------------------------------------------------------------------
    # Test 13 — Same check-in and check-out
    # check_in == check_out. Expected: REJECT
    # -------------------------------------------------------------------------
    def test_13_same_checkin_checkout(self):
        same_date = datetime.datetime(2026, 10, 10, 14, 0)
        with self.assertRaises(ValidationError):
            self.env['hotel.reservation'].create({
                'partner_id': self.partner.id,
                'hotel_id': self.hotel.id,
                'check_in': same_date,
                'check_out': same_date,
                'line_ids': [
                    (0, 0, {
                        'room_id': self.room_101.id,
                        'room_category_id': self.category_deluxe.id,
                        'rate_plan_id': self.rate_plan.id,
                        'check_in': same_date,
                        'check_out': same_date,
                    })
                ]
            })

    # -------------------------------------------------------------------------
    # Test 14 — Check-out earlier than check-in
    # check_in > check_out. Expected: REJECT
    # -------------------------------------------------------------------------
    def test_14_checkout_before_checkin(self):
        in_date = datetime.datetime(2026, 10, 15, 14, 0)
        out_date = datetime.datetime(2026, 10, 10, 11, 0)
        with self.assertRaises(ValidationError):
            self.env['hotel.reservation'].create({
                'partner_id': self.partner.id,
                'hotel_id': self.hotel.id,
                'check_in': in_date,
                'check_out': out_date,
                'line_ids': [
                    (0, 0, {
                        'room_id': self.room_101.id,
                        'room_category_id': self.category_deluxe.id,
                        'rate_plan_id': self.rate_plan.id,
                        'check_in': in_date,
                        'check_out': out_date,
                    })
                ]
            })

    # -------------------------------------------------------------------------
    # Test 15 — Room type mismatch
    # Line category = Deluxe, Selected room = Standard. Expected: REJECT
    # -------------------------------------------------------------------------
    def test_15_room_type_mismatch(self):
        in_date = datetime.datetime(2026, 10, 10, 14, 0)
        out_date = datetime.datetime(2026, 10, 15, 11, 0)
        with self.assertRaises(ValidationError):
            self._create_reservation(
                in_date,
                out_date,
                self.room_standard, # Standard room
                category=self.category_deluxe, # Deluxe category
                state='draft',
            )

    # -------------------------------------------------------------------------
    # Test 16 — Guest capacity exceeded
    # Category max_adults = 2. Requested adults = 3. Expected: REJECT
    # -------------------------------------------------------------------------
    def test_16_guest_capacity_exceeded(self):
        in_date = datetime.datetime(2026, 10, 10, 14, 0)
        out_date = datetime.datetime(2026, 10, 15, 11, 0)
        with self.assertRaises(ValidationError):
            self._create_reservation(
                in_date,
                out_date,
                self.room_101,
                adults=3, # exceeds max_adults=2
                state='draft',
            )

    # -------------------------------------------------------------------------
    # Test 17 — Multi-room duplicate room overlap within same reservation
    # Same room assigned twice with overlapping dates. Expected: REJECT
    # -------------------------------------------------------------------------
    def test_17_multi_room_duplicate_same_reservation(self):
        in_date = datetime.datetime(2026, 10, 10, 14, 0)
        out_date = datetime.datetime(2026, 10, 15, 11, 0)

        with self.assertRaises(ValidationError):
            self.env['hotel.reservation'].create({
                'partner_id': self.partner.id,
                'hotel_id': self.hotel.id,
                'check_in': in_date,
                'check_out': out_date,
                'line_ids': [
                    (0, 0, {
                        'room_id': self.room_101.id,
                        'room_category_id': self.category_deluxe.id,
                        'rate_plan_id': self.rate_plan.id,
                        'check_in': in_date,
                        'check_out': out_date,
                        'adults': 1,
                    }),
                    (0, 0, {
                        'room_id': self.room_101.id, # Duplicate room 101
                        'room_category_id': self.category_deluxe.id,
                        'rate_plan_id': self.rate_plan.id,
                        'check_in': in_date,
                        'check_out': out_date,
                        'adults': 1,
                    }),
                ]
            })

    # -------------------------------------------------------------------------
    # Test 18 — Checked out reservation does not block future bookings
    # Completed/checked-out reservation should not block availability.
    # -------------------------------------------------------------------------
    def test_18_checked_out_does_not_block(self):
        in_date = datetime.datetime(2026, 10, 10, 14, 0)
        out_date = datetime.datetime(2026, 10, 15, 11, 0)

        res = self._create_reservation(in_date, out_date, self.room_101, state='confirmed')
        res.action_reserve()
        res.action_check_in()
        res.action_check_out()
        res.action_complete()
        self.assertEqual(res.state, 'completed')

        # New reservation for the same dates and room must now be allowed
        res2 = self._create_reservation(in_date, out_date, self.room_101, state='draft')
        res2.action_confirm()
        self.assertEqual(res2.state, 'confirmed')

    # -------------------------------------------------------------------------
    # Test 19 — Check-in validation
    # A reservation cannot be checked in if the room is not ready / dirty
    # -------------------------------------------------------------------------
    def test_19_check_in_validation(self):
        in_date = datetime.datetime(2026, 10, 10, 14, 0)
        out_date = datetime.datetime(2026, 10, 15, 11, 0)

        res = self._create_reservation(in_date, out_date, self.room_101, state='confirmed')
        res.action_reserve()
        self.assertEqual(res.state, 'reserved')

        # Put room under dirty status (operational status preventing check-in)
        self.room_101.write({'status': 'dirty'})
        with self.assertRaises(ValidationError):
            res.action_check_in()

        # Reset room
        self.room_101.write({'status': 'available'})
        res.action_check_in()
        self.assertEqual(res.state, 'checked_in')

    # -------------------------------------------------------------------------
    # Test 20 — Room selection UI / available_room_ids computation
    # -------------------------------------------------------------------------
    def test_20_available_room_ids_computation(self):
        in_date = datetime.datetime(2026, 10, 10, 14, 0)
        out_date = datetime.datetime(2026, 10, 15, 11, 0)

        # 1. Existing confirmed booking on room 101
        self._create_reservation(in_date, out_date, self.room_101, state='confirmed')

        # 2. Put room 102 in maintenance
        self.room_102.write({'status': 'maintenance'})

        # 3. Create a virtual draft line for same dates, Deluxe category, 1 adult
        res = self.env['hotel.reservation'].create({
            'partner_id': self.partner.id,
            'hotel_id': self.hotel.id,
            'check_in': in_date,
            'check_out': out_date,
        })
        line = self.env['hotel.reservation.line'].new({
            'reservation_id': res,
            'hotel_id': self.hotel,
            'room_category_id': self.category_deluxe,
            'rate_plan_id': self.rate_plan,
            'check_in': in_date,
            'check_out': out_date,
            'adults': 1,
            'children': 0,
        })

        # available_room_ids must NOT include room_101 (overlap) and room_102 (maintenance)
        line._compute_available_room_ids()
        self.assertNotIn(self.room_101, line.available_room_ids._origin)
        self.assertNotIn(self.room_102, line.available_room_ids._origin)
        self.assertNotIn(self.room_standard, line.available_room_ids._origin) # Standard category mismatch

        # 4. Check back-to-back dates (15 Oct to 20 Oct): room 101 MUST be available
        line.check_in = datetime.datetime(2026, 10, 15, 14, 0)
        line.check_out = datetime.datetime(2026, 10, 20, 11, 0)
        line._compute_available_room_ids()
        self.assertIn(self.room_101, line.available_room_ids._origin)

        # 5. Check capacity filter: if adults=3 (exceeds deluxe max_adults=2), room 101 must not be available
        line.adults = 3
        line._compute_available_room_ids()
        self.assertNotIn(self.room_101, line.available_room_ids._origin)

        # Reset room 102
        self.room_102.write({'status': 'available'})
