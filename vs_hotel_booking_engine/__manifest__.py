{
    'name': 'Hotel Online Booking Engine & Guest Portal',
    'version': '20.0.1.0.0',
    'category': 'Hotel Management',
    'summary': 'Dynamic Multi-Hotel Online Booking Engine & Self-Service Guest Portal for Odoo 20',
    'description': """
Hotel Online Booking Engine & Guest Portal
==========================================
Modern, responsive, mobile-first hospitality booking engine and guest portal for Odoo 20:
- Multi-Hotel Support: Seamless booking across multiple hotel properties.
- Dynamic Multi-Room & Multi-Category Selection: Book multiple rooms across different categories in one reservation.
- Logo-Driven Dynamic Theme: Booking pages and portal automatically inherit brand colors from the hotel's uploaded logo.
- Clean Itemized Room Pricing: Transparent room rates, nights, taxes, and totals without service clutter.
- Guest Onboarding & Identification: Captures CNIC / Passport / National ID, address, and accompanying guests.
- Flexible Advance Booking Payment: Configurable policy (Optional vs Mandatory) and deposit percentage with Pay Now vs Pay Later options.
- Self-Service Guest Portal: Real-time stay monitoring, folio breakdown, PDF voucher downloads, and pre-arrival room switching.
    """,
    'author': 'Veritiesoft',
    'website': 'https://www.veritiesoft.com',
    'license': 'LGPL-3',
    'depends': [
        'vs_hotel_management',
        'portal',
        'payment',
        'website',
        'web',
    ],
    'data': [
        'security/ir.access.csv',
        'data/website_menu_data.xml',
        'data/mail_template_booking.xml',
        'views/hotel_hotel_views.xml',
        'views/res_config_settings_views.xml',
        'views/hotel_reservation_views.xml',
        'views/booking_engine_templates.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'vs_hotel_booking_engine/static/src/css/booking_engine.css',
            'vs_hotel_booking_engine/static/src/js/booking_engine.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
