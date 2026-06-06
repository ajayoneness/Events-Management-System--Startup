"""
Management command: python manage.py seed_data

Clears ALL existing data and populates the database with realistic dummy data
for testing. Creates:
  - 1 superuser (admin / admin123)
  - 3 regular users
  - 10 events across all categories
  - 2–3 ticket types per event (Normal / Premium / VIP)
  - 12+ bookings in various statuses
  - 5 coupon codes
  - 2 organizer profiles
  - 3 team members
  - Site settings stub (WhatsApp/Gmail remain blank — fill from Admin)
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.management import call_command
from decimal import Decimal
import datetime


class Command(BaseCommand):
    help = 'Wipe all data and seed the database with realistic dummy data'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('⚠️  Flushing all existing data…'))
        call_command('flush', '--no-input', verbosity=0)
        self.stdout.write(self.style.SUCCESS('✅  Database cleared'))

        from events.models import (
            Event, Booking, TicketType, CouponCode,
            OrganizerProfile, TeamMember, SiteSettings,
        )

        now = timezone.now()

        # ── Site Settings ──────────────────────────────────────────────────
        self.stdout.write('   Creating site settings…')
        SiteSettings.objects.create(
            pk=1,
            site_name='EventHub',
            site_url='http://127.0.0.1:8000',
            support_email='support@eventhub.in',
            support_phone='+91 98765 43210',
            # Leave API keys blank — fill from Admin dashboard
            whatsapp_enabled=False,
            email_enabled=False,
            razorpay_enabled=True,
            razorpay_key_id='rzp_test_tPhc333asPKtv6',
            razorpay_key_secret='UVSxUflxDlLM9dgEHGBxVok2',
        )

        # ── Users ──────────────────────────────────────────────────────────
        self.stdout.write('   Creating users…')
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@eventhub.in',
            password='admin123',
            first_name='Admin',
            last_name='EventHub',
        )

        u1 = User.objects.create_user(
            username='rahul_sharma',
            email='rahul@example.com',
            password='test1234',
            first_name='Rahul',
            last_name='Sharma',
        )
        u2 = User.objects.create_user(
            username='priya_patel',
            email='priya@example.com',
            password='test1234',
            first_name='Priya',
            last_name='Patel',
        )
        u3 = User.objects.create_user(
            username='arjun_mehta',
            email='arjun@example.com',
            password='test1234',
            first_name='Arjun',
            last_name='Mehta',
        )
        self.stdout.write(self.style.SUCCESS(
            '   ✅ Users — admin/admin123, rahul_sharma/test1234, priya_patel/test1234, arjun_mehta/test1234'
        ))

        # ── Organizer Profiles ─────────────────────────────────────────────
        self.stdout.write('   Creating organizer profiles…')
        OrganizerProfile.objects.create(
            user=u1,
            organization_name='Sharma Events Pvt Ltd',
            mobile_number='+91 98100 11223',
            bank_account_holder_name='Rahul Sharma',
            bank_account_number='1234567890123456',
            bank_ifsc_code='SBIN0001234',
            bank_name='State Bank of India',
            pan_card_number='ABCDE1234F',
            aadhaar_number='123456789012',
            status='verified',
            wallet_balance=Decimal('12500.00'),
        )
        OrganizerProfile.objects.create(
            user=u2,
            organization_name='Priya Cultural Events',
            mobile_number='+91 99887 76655',
            bank_account_holder_name='Priya Patel',
            bank_account_number='9876543210987654',
            bank_ifsc_code='HDFC0005678',
            bank_name='HDFC Bank',
            pan_card_number='FGHIJ5678K',
            aadhaar_number='987654321098',
            status='pending',
            wallet_balance=Decimal('0.00'),
        )

        # ── Team Members ───────────────────────────────────────────────────
        self.stdout.write('   Creating team members…')
        TeamMember.objects.create(
            organizer=u1,
            name='Suresh Kumar',
            email='suresh@example.com',
            phone='+91 90000 11111',
            role='verifier',
        )
        TeamMember.objects.create(
            organizer=u1,
            name='Deepa Singh',
            email='deepa@example.com',
            phone='+91 91111 22222',
            role='manager',
        )
        TeamMember.objects.create(
            organizer=u2,
            name='Ravi Nair',
            email='ravi@example.com',
            phone='+91 92222 33333',
            role='verifier',
        )

        # ── Events ─────────────────────────────────────────────────────────
        self.stdout.write('   Creating events…')

        def make_dt(days_ahead, hour=18, minute=0):
            return now + datetime.timedelta(days=days_ahead)

        events_data = [
            {
                'title': 'Arijit Singh Live in Concert',
                'description': (
                    'Experience the magical voice of Arijit Singh live on stage! '
                    'This mega concert brings together India\'s most beloved singer for an '
                    'unforgettable evening of soulful melodies, hit Bollywood numbers, and '
                    'intimate acoustic performances. Get ready for a night filled with emotions, '
                    'lights, and music that will stay with you forever.'
                ),
                'category': 'music',
                'date': make_dt(10),
                'end_date': make_dt(10) + datetime.timedelta(hours=3),
                'venue': 'MMRDA Grounds, BKC',
                'address': 'Bandra Kurla Complex, Mumbai, Maharashtra 400051',
                'latitude': 19.0596,
                'longitude': 72.8656,
                'price': Decimal('1500.00'),
                'total_seats': 5000,
                'available_seats': 3200,
                'image': 'https://images.unsplash.com/photo-1501386761578-eaa54b9b0ac5?w=800&q=80',
                'organizer': 'Sharma Events Pvt Ltd',
                'organizer_user': u1,
                'status': 'published',
                'is_free': False,
                'is_approved': True,
            },
            {
                'title': 'Google I/O Extended — Mumbai 2025',
                'description': (
                    'Join us for Google I/O Extended Mumbai — the city\'s biggest developer '
                    'event! Watch live streams of Google I/O keynotes, attend hands-on '
                    'workshops on Gemini AI, Flutter, Firebase, and Android. Network with '
                    '500+ developers, engineers, and tech enthusiasts from across India. '
                    'Snacks and refreshments included.'
                ),
                'category': 'tech',
                'date': make_dt(7),
                'end_date': make_dt(7) + datetime.timedelta(hours=8),
                'venue': 'Google India Office, Powai',
                'address': 'Tower 8, Equinox Business Park, Kurla W, Mumbai 400070',
                'latitude': 19.1176,
                'longitude': 72.9060,
                'price': Decimal('299.00'),
                'total_seats': 500,
                'available_seats': 120,
                'image': 'https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=800&q=80',
                'organizer': 'GDG Mumbai',
                'organizer_user': u2,
                'status': 'published',
                'is_free': False,
                'is_approved': True,
            },
            {
                'title': 'IPL After Party — Mumbai Indians Celebration',
                'description': (
                    'Celebrate Mumbai Indians\' championship win with an epic after-party! '
                    'Live DJ, celebrity appearances, unlimited food & drinks (included in '
                    'ticket price), and exclusive fan merchandise. Come dressed in your blue '
                    'and gold and party the night away with fellow Paltan!'
                ),
                'category': 'sports',
                'date': make_dt(14),
                'venue': 'Jio World Convention Centre',
                'address': 'G Block, BKC, Bandra East, Mumbai 400051',
                'latitude': 19.0579,
                'longitude': 72.8655,
                'price': Decimal('2500.00'),
                'total_seats': 1000,
                'available_seats': 450,
                'image': 'https://images.unsplash.com/photo-1540747913346-19212a4b733d?w=800&q=80',
                'organizer': 'Sharma Events Pvt Ltd',
                'organizer_user': u1,
                'status': 'published',
                'is_free': False,
                'is_approved': True,
            },
            {
                'title': 'Mumbai Food Festival 2025',
                'description': (
                    'India\'s largest food festival returns to Mumbai! Over 200 food stalls '
                    'featuring cuisines from every corner of India and the world. Enjoy live '
                    'cooking demonstrations by celebrity chefs, food competitions, '
                    'masterclasses, and artisanal markets. Kid-friendly with dedicated '
                    'children\'s activity zones.'
                ),
                'category': 'food',
                'date': make_dt(21),
                'end_date': make_dt(23),
                'venue': 'Bandra Bandstand Promenade',
                'address': 'Bandstand, Bandra West, Mumbai 400050',
                'latitude': 19.0549,
                'longitude': 72.8199,
                'price': Decimal('0.00'),
                'total_seats': 10000,
                'available_seats': 7500,
                'image': 'https://images.unsplash.com/photo-1555939594-58d7cb561ad1?w=800&q=80',
                'organizer': 'Mumbai Tourism Board',
                'organizer_user': None,
                'status': 'published',
                'is_free': True,
                'is_approved': True,
            },
            {
                'title': 'Contemporary Art Showcase — Mumbai',
                'description': (
                    'Step into the world of contemporary Indian art at this exclusive '
                    'showcase featuring 50+ artists from across the country. The exhibition '
                    'includes paintings, sculptures, digital art, and immersive installations. '
                    'Guided tours available every hour. A must-visit for art lovers and '
                    'collectors alike.'
                ),
                'category': 'art',
                'date': make_dt(5),
                'end_date': make_dt(7),
                'venue': 'National Gallery of Modern Art',
                'address': 'Sir Cowasji Jehangir Public Hall, MG Rd, Fort, Mumbai 400001',
                'latitude': 18.9281,
                'longitude': 72.8322,
                'price': Decimal('350.00'),
                'total_seats': 300,
                'available_seats': 210,
                'image': 'https://images.unsplash.com/photo-1536924940846-227afb31e2a5?w=800&q=80',
                'organizer': 'Priya Cultural Events',
                'organizer_user': u2,
                'status': 'published',
                'is_free': False,
                'is_approved': True,
            },
            {
                'title': 'Startup India Summit 2025',
                'description': (
                    'Connect with India\'s top entrepreneurs, VCs, and innovators at the '
                    'Startup India Summit 2025. Keynotes from unicorn founders, panel '
                    'discussions on AI & deep tech, investor pitching sessions, and '
                    'networking dinners. Last year saw 3,000+ attendees and ₹50Cr in '
                    'funding deals signed on the floor!'
                ),
                'category': 'business',
                'date': make_dt(30),
                'end_date': make_dt(31),
                'venue': 'Bombay Exhibition Centre (NESCO)',
                'address': 'Western Express Hwy, Goregaon East, Mumbai 400063',
                'latitude': 19.1538,
                'longitude': 72.8487,
                'price': Decimal('4999.00'),
                'total_seats': 2000,
                'available_seats': 1100,
                'image': 'https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800&q=80',
                'organizer': 'Sharma Events Pvt Ltd',
                'organizer_user': u1,
                'status': 'published',
                'is_free': False,
                'is_approved': True,
            },
            {
                'title': 'Yoga & Wellness Weekend Retreat',
                'description': (
                    'Rejuvenate your mind, body, and soul at this 2-day wellness retreat. '
                    'Sessions include morning yoga, guided meditation, breathwork, '
                    'Ayurvedic nutrition workshops, and sound healing. Led by certified '
                    'instructors with 10+ years of experience. All levels welcome. '
                    'Organic meals and herbal teas included.'
                ),
                'category': 'other',
                'date': make_dt(12),
                'end_date': make_dt(13),
                'venue': 'Aamby Valley Resort, Pune',
                'address': 'Aamby Valley City, Sahyadri Range, Pune 412205',
                'latitude': 18.6161,
                'longitude': 73.4053,
                'price': Decimal('1200.00'),
                'total_seats': 80,
                'available_seats': 35,
                'image': 'https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=800&q=80',
                'organizer': 'Priya Cultural Events',
                'organizer_user': u2,
                'status': 'published',
                'is_free': False,
                'is_approved': True,
            },
            {
                'title': 'Coldplay World Tour — Mumbai Night 2',
                'description': (
                    'After a sold-out Night 1, Coldplay returns for a second magical night '
                    'in Mumbai! Experience the Music of the Spheres World Tour live — '
                    'stunning visuals, eco-friendly LED wristbands, confetti cannons, and '
                    'hit songs from every era of their legendary career. This is the '
                    'concert of a lifetime.'
                ),
                'category': 'music',
                'date': make_dt(45),
                'venue': 'DY Patil Stadium, Navi Mumbai',
                'address': 'Dr DY Patil Sports Academy, Nerul, Navi Mumbai 400706',
                'latitude': 19.0330,
                'longitude': 73.0297,
                'price': Decimal('3500.00'),
                'total_seats': 40000,
                'available_seats': 8000,
                'image': 'https://images.unsplash.com/photo-1459749411175-04bf5292ceea?w=800&q=80',
                'organizer': 'BookMyShow Live',
                'organizer_user': u1,
                'status': 'published',
                'is_free': False,
                'is_approved': True,
            },
            {
                'title': 'Python & Django Workshop — Beginner to Pro',
                'description': (
                    'A full-day intensive workshop covering Python basics to building '
                    'production-ready Django applications. Topics: Python fundamentals, '
                    'Django ORM, REST APIs with DRF, deployment on Heroku/AWS, and best '
                    'practices. Laptops required. Lunch and refreshments provided. '
                    'Certificate on completion.'
                ),
                'category': 'tech',
                'date': make_dt(8),
                'venue': 'IIT Bombay — Computer Science Dept',
                'address': 'Powai, Mumbai, Maharashtra 400076',
                'latitude': 19.1334,
                'longitude': 72.9133,
                'price': Decimal('0.00'),
                'total_seats': 60,
                'available_seats': 15,
                'image': 'https://images.unsplash.com/photo-1517180102446-f3ece451e9d8?w=800&q=80',
                'organizer': 'IIT Bombay Tech Club',
                'organizer_user': u3,
                'status': 'published',
                'is_free': True,
                'is_approved': True,
            },
            {
                'title': 'New Year\'s Eve Gala 2026',
                'description': (
                    'Welcome 2026 in style at the most exclusive New Year\'s Eve party in '
                    'Mumbai! Black-tie optional. Features a 7-course gala dinner, live '
                    'band, DJ, countdown celebration with fireworks, and champagne toast '
                    'at midnight. Dress code: formal/semi-formal. Table bookings available.'
                ),
                'category': 'other',
                'date': make_dt(60),
                'venue': 'The Taj Mahal Palace, Mumbai',
                'address': 'Apollo Bandar, Colaba, Mumbai 400001',
                'latitude': 18.9220,
                'longitude': 72.8347,
                'price': Decimal('8500.00'),
                'total_seats': 400,
                'available_seats': 180,
                'image': 'https://images.unsplash.com/photo-1482442120256-9c03866de390?w=800&q=80',
                'organizer': 'Sharma Events Pvt Ltd',
                'organizer_user': u1,
                'status': 'published',
                'is_free': False,
                'is_approved': True,
            },
        ]

        created_events = []
        for ed in events_data:
            e = Event.objects.create(**ed)
            created_events.append(e)

        self.stdout.write(self.style.SUCCESS(f'   ✅ {len(created_events)} events created'))

        # ── Ticket Types ───────────────────────────────────────────────────
        self.stdout.write('   Creating ticket types…')

        ticket_configs = {
            0: [  # Arijit Singh Concert
                ('Normal', 'normal', Decimal('1500'), 3000, 2000),
                ('Premium', 'premium', Decimal('3000'), 1500, 1000),
                ('VIP', 'vip', Decimal('8000'), 500, 200),
            ],
            1: [  # Google I/O Extended
                ('Standard', 'normal', Decimal('299'), 400, 100),
                ('Early Bird Premium', 'premium', Decimal('499'), 100, 20),
            ],
            2: [  # IPL After Party
                ('General Entry', 'normal', Decimal('2500'), 700, 350),
                ('VIP Lounge', 'vip', Decimal('6000'), 300, 100),
            ],
            4: [  # Art Showcase
                ('General', 'normal', Decimal('350'), 250, 180),
                ('Guided Tour', 'premium', Decimal('600'), 50, 30),
            ],
            5: [  # Startup Summit
                ('Delegate Pass', 'normal', Decimal('4999'), 1500, 850),
                ('Investor Pass', 'premium', Decimal('12000'), 300, 150),
                ('Speaker/VIP', 'vip', Decimal('0'), 200, 100),
            ],
            7: [  # Coldplay
                ('General Standing', 'normal', Decimal('3500'), 30000, 6000),
                ('Premium Seated', 'premium', Decimal('7500'), 8000, 1500),
                ('VIP Pit', 'vip', Decimal('15000'), 2000, 500),
            ],
            9: [  # NYE Gala
                ('Regular Table (4 seats)', 'normal', Decimal('8500'), 300, 140),
                ('Premium Table (6 seats)', 'premium', Decimal('15000'), 80, 30),
                ('Royal Suite Table', 'vip', Decimal('35000'), 20, 10),
            ],
        }

        for idx, tiers in ticket_configs.items():
            event = created_events[idx]
            for name, tier, price, total, avail in tiers:
                TicketType.objects.create(
                    event=event,
                    name=name,
                    tier=tier,
                    price=price,
                    total_seats=total,
                    available_seats=avail,
                    is_active=True,
                )

        self.stdout.write(self.style.SUCCESS('   ✅ Ticket types created'))

        # ── Coupon Codes ───────────────────────────────────────────────────
        self.stdout.write('   Creating coupon codes…')

        CouponCode.objects.create(
            code='WELCOME20',
            discount_type='percentage',
            discount_value=Decimal('20'),
            max_uses=500,
            valid_from=now,
            valid_until=now + datetime.timedelta(days=90),
            minimum_amount=Decimal('500'),
            is_active=True,
        )
        CouponCode.objects.create(
            code='FLAT500',
            discount_type='flat',
            discount_value=Decimal('500'),
            max_uses=200,
            valid_from=now,
            valid_until=now + datetime.timedelta(days=60),
            minimum_amount=Decimal('2000'),
            is_active=True,
        )
        CouponCode.objects.create(
            code='TECH50',
            discount_type='percentage',
            discount_value=Decimal('50'),
            max_uses=100,
            valid_from=now,
            valid_until=now + datetime.timedelta(days=30),
            minimum_amount=Decimal('0'),
            event=created_events[1],  # Google I/O
            is_active=True,
        )
        CouponCode.objects.create(
            code='STUDENT15',
            discount_type='percentage',
            discount_value=Decimal('15'),
            max_uses=1000,
            valid_from=now,
            valid_until=now + datetime.timedelta(days=120),
            minimum_amount=Decimal('200'),
            is_active=True,
        )
        CouponCode.objects.create(
            code='EXPIRED10',
            discount_type='percentage',
            discount_value=Decimal('10'),
            max_uses=100,
            valid_from=now - datetime.timedelta(days=30),
            valid_until=now - datetime.timedelta(days=1),
            minimum_amount=Decimal('0'),
            is_active=False,  # Expired
        )

        self.stdout.write(self.style.SUCCESS('   ✅ Coupon codes: WELCOME20 | FLAT500 | TECH50 | STUDENT15'))

        # ── Bookings ───────────────────────────────────────────────────────
        self.stdout.write('   Creating bookings…')
        from events.utils import generate_qr_code

        bookings_data = [
            # Confirmed bookings for u1 (rahul)
            {
                'event': created_events[1],  # Google I/O
                'user': u1,
                'name': 'Rahul Sharma',
                'email': 'rahul@example.com',
                'phone': '+919810011223',
                'number_of_tickets': 2,
                'total_amount': Decimal('598.00'),
                'status': 'confirmed',
                'email_sent': True,
                'whatsapp_sent': True,
                'razorpay_order_id': 'order_dummy_001',
                'razorpay_payment_id': 'pay_dummy_001',
            },
            {
                'event': created_events[4],  # Art Showcase
                'user': u1,
                'name': 'Rahul Sharma',
                'email': 'rahul@example.com',
                'phone': '+919810011223',
                'number_of_tickets': 1,
                'total_amount': Decimal('350.00'),
                'status': 'confirmed',
                'email_sent': True,
                'whatsapp_sent': False,
                'razorpay_order_id': 'order_dummy_002',
                'razorpay_payment_id': 'pay_dummy_002',
            },
            {
                'event': created_events[5],  # Startup Summit
                'user': u1,
                'name': 'Rahul Sharma',
                'email': 'rahul@example.com',
                'phone': '+919810011223',
                'number_of_tickets': 1,
                'total_amount': Decimal('4999.00'),
                'status': 'confirmed',
                'email_sent': True,
                'whatsapp_sent': True,
                'razorpay_order_id': 'order_dummy_003',
                'razorpay_payment_id': 'pay_dummy_003',
            },
            # Confirmed bookings for u2 (priya)
            {
                'event': created_events[0],  # Arijit Singh
                'user': u2,
                'name': 'Priya Patel',
                'email': 'priya@example.com',
                'phone': '+919988776655',
                'number_of_tickets': 3,
                'total_amount': Decimal('4500.00'),
                'status': 'confirmed',
                'email_sent': True,
                'whatsapp_sent': True,
                'razorpay_order_id': 'order_dummy_004',
                'razorpay_payment_id': 'pay_dummy_004',
            },
            {
                'event': created_events[6],  # Yoga Retreat
                'user': u2,
                'name': 'Priya Patel',
                'email': 'priya@example.com',
                'phone': '+919988776655',
                'number_of_tickets': 1,
                'total_amount': Decimal('1200.00'),
                'status': 'confirmed',
                'email_sent': True,
                'whatsapp_sent': False,
                'razorpay_order_id': 'order_dummy_005',
                'razorpay_payment_id': 'pay_dummy_005',
            },
            # Confirmed for u3 (arjun)
            {
                'event': created_events[2],  # IPL After Party
                'user': u3,
                'name': 'Arjun Mehta',
                'email': 'arjun@example.com',
                'phone': '+919222233333',
                'number_of_tickets': 2,
                'total_amount': Decimal('5000.00'),
                'status': 'confirmed',
                'email_sent': True,
                'whatsapp_sent': True,
                'razorpay_order_id': 'order_dummy_006',
                'razorpay_payment_id': 'pay_dummy_006',
            },
            {
                'event': created_events[7],  # Coldplay Night 2
                'user': u3,
                'name': 'Arjun Mehta',
                'email': 'arjun@example.com',
                'phone': '+919222233333',
                'number_of_tickets': 4,
                'total_amount': Decimal('14000.00'),
                'status': 'confirmed',
                'email_sent': False,
                'whatsapp_sent': False,
                'razorpay_order_id': 'order_dummy_007',
                'razorpay_payment_id': 'pay_dummy_007',
            },
            # Pending booking
            {
                'event': created_events[9],  # NYE Gala
                'user': u1,
                'name': 'Rahul Sharma',
                'email': 'rahul@example.com',
                'phone': '+919810011223',
                'number_of_tickets': 1,
                'total_amount': Decimal('8500.00'),
                'status': 'pending',
                'email_sent': False,
                'whatsapp_sent': False,
                'razorpay_order_id': 'order_dummy_008',
                'razorpay_payment_id': '',
            },
            # Cancelled booking
            {
                'event': created_events[3],  # Food Festival (free)
                'user': u2,
                'name': 'Priya Patel',
                'email': 'priya@example.com',
                'phone': '+919988776655',
                'number_of_tickets': 2,
                'total_amount': Decimal('0.00'),
                'status': 'cancelled',
                'email_sent': False,
                'whatsapp_sent': False,
                'razorpay_order_id': '',
                'razorpay_payment_id': '',
            },
            # Failed booking
            {
                'event': created_events[0],  # Arijit Singh
                'user': u3,
                'name': 'Arjun Mehta',
                'email': 'arjun@example.com',
                'phone': '+919222233333',
                'number_of_tickets': 2,
                'total_amount': Decimal('3000.00'),
                'status': 'failed',
                'email_sent': False,
                'whatsapp_sent': False,
                'razorpay_order_id': 'order_dummy_010',
                'razorpay_payment_id': 'pay_failed_010',
            },
            # Refunded booking
            {
                'event': created_events[5],  # Startup Summit
                'user': u2,
                'name': 'Priya Patel',
                'email': 'priya@example.com',
                'phone': '+919988776655',
                'number_of_tickets': 1,
                'total_amount': Decimal('4999.00'),
                'status': 'refunded',
                'email_sent': True,
                'whatsapp_sent': True,
                'razorpay_order_id': 'order_dummy_011',
                'razorpay_payment_id': 'pay_dummy_011',
                'refund_reason': 'Customer requested cancellation 3 days before event.',
                'refunded_at': now - datetime.timedelta(days=2),
            },
        ]

        qr_count = 0
        for bd in bookings_data:
            refund_reason = bd.pop('refund_reason', '')
            refunded_at = bd.pop('refunded_at', None)
            b = Booking.objects.create(refund_reason=refund_reason, refunded_at=refunded_at, **bd)
            if b.status == 'confirmed':
                try:
                    generate_qr_code(b)
                    qr_count += 1
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'      QR skipped for {b.name}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'   ✅ {len(bookings_data)} bookings created, {qr_count} QR codes generated'
        ))

        # ── Summary ────────────────────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 58))
        self.stdout.write(self.style.SUCCESS('  ✅  Seed complete!'))
        self.stdout.write(self.style.SUCCESS('=' * 58))
        self.stdout.write('')
        self.stdout.write('  🔐 Admin login:')
        self.stdout.write('     URL:      http://127.0.0.1:8000/admin/')
        self.stdout.write('     Username: admin')
        self.stdout.write('     Password: admin123')
        self.stdout.write('')
        self.stdout.write('  👤 Test users (all password: test1234):')
        self.stdout.write('     rahul_sharma  | rahul@example.com')
        self.stdout.write('     priya_patel   | priya@example.com')
        self.stdout.write('     arjun_mehta   | arjun@example.com')
        self.stdout.write('')
        self.stdout.write('  🎫 Coupon codes:')
        self.stdout.write('     WELCOME20  — 20% off (min ₹500)')
        self.stdout.write('     FLAT500    — ₹500 off (min ₹2000)')
        self.stdout.write('     TECH50     — 50% off Google I/O only')
        self.stdout.write('     STUDENT15  — 15% off any event')
        self.stdout.write('')
        self.stdout.write('  🔑 Configure WhatsApp & Gmail API keys:')
        self.stdout.write('     Admin → Events → Site Settings')
        self.stdout.write(self.style.SUCCESS('=' * 58))
