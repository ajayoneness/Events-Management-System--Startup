# Event Booking System

A comprehensive Django-based web application for event management and ticket booking with integrated payment processing. Developed by CodeAJ Marketplace.

## Important Notice

**PROPRIETARY SOFTWARE**

This software is proprietary and confidential. Unauthorized distribution, reproduction, or sharing of this software, in whole or in part, is strictly prohibited. This software is provided for authorized use only.

For licensing inquiries, please contact:
- Email: contact@codeaj.com
- Phone: +918603862290

---

## Features

### Core Booking
- **User Authentication** — Secure registration, login, and profile management with booking history
- **Event Browsing** — Browse, search, and filter events by category, location, and date
- **Multiple Ticket Types** — Normal / Premium / VIP ticket tiers per event with individual pricing and seat counts
- **Coupon Code Discounts** — Percentage or flat-amount coupons with AJAX real-time validation, usage limits, expiry, and minimum amount rules
- **Booking System** — Real-time seat availability tracking and booking with Razorpay payment integration
- **QR Code Tickets** — Auto-generated QR codes for contactless entry validation
- **Calendar Integration** — Download event details as iCal (.ics) for Google Calendar / Apple Calendar

### New Features
- **Sales Dashboard** — Staff-only dashboard at `/dashboard/` showing total revenue, confirmed/pending bookings, top events by revenue, booking status breakdown, and an event management table
- **Attendee Data Export (CSV)** — Export confirmed attendees for any event to a CSV spreadsheet (name, email, phone, ticket type, amount paid, coupon used, payment ID) via `/event/<id>/export/`
- **Refund Management** — Dedicated page at `/refunds/` for staff to process refunds (with reason), cancel bookings, and filter by status. Automatically restores seat count on refund
- **Offline Ticket Download** — Printable e-ticket page at `/booking/<id>/ticket/` with full event details, QR code, and a "Download / Print" button (save as PDF via browser)
- **Email Reminders** — Send bulk reminder emails to all confirmed attendees of an event via `/event/<id>/send-reminder/`
- **Payout Wallet** — Organizer wallet at `/wallet/` showing available balance, payout request form (requires verified KYC + bank details), and payout history with status tracking
- **Notifications** — Email (Gmail SMTP) and WhatsApp Business API confirmation messages on booking confirmation

### Admin & Management
- **Site Settings** — Configure Razorpay keys, Gmail SMTP, WhatsApp API, and site info from a single admin panel
- **Organizer KYC** — Organizer profiles with bank details, PAN/Aadhaar verification, and wallet balance
- **Team Members** — Assign verifiers, managers, and support staff to an organizer
- **Coupon Management** — Create and manage coupon codes with event-specific or global scope
- **Payout Request Admin** — Admin can approve/reject payout requests and mark them as paid
- **Booking Admin Actions** — Export CSV, send email, send WhatsApp, mark refunded — all from Django admin

---

## Installation

1. Clone or extract the project, then open a terminal in the project folder.

2. Create and activate a virtual environment:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables — create a `.env` file in the project root:
```
SECRET_KEY=your_django_secret_key
DEBUG=True
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
```

5. Run migrations:
```bash
python manage.py migrate
```

6. (Optional) Seed the database with sample data:
```bash
python manage.py seed_data
```

7. Create a superuser:
```bash
python manage.py createsuperuser
```

8. Start the development server:
```bash
python manage.py runserver
```

9. Open http://127.0.0.1:8000/

---

## URL Reference

| URL | Description | Access |
|-----|-------------|--------|
| `/` | Home page with upcoming events | Public |
| `/events/` | Browse all events with category filters | Public |
| `/event/<id>/` | Event detail + booking form | Login required |
| `/my-bookings/` | User's booking history | Login required |
| `/booking/<id>/ticket/` | Printable / downloadable ticket | Owner / Staff |
| `/booking/<id>/success/` | Booking confirmation + QR code | Owner |
| `/booking/<id>/calendar/` | Download iCal file | Owner |
| `/search-booking/` | Find booking by email (anonymous) | Public |
| `/dashboard/` | Sales dashboard | Staff only |
| `/refunds/` | Refund management | Staff only |
| `/event/<id>/export/` | Export attendees to CSV | Staff only |
| `/event/<id>/send-reminder/` | Send email reminder to attendees | Staff only |
| `/wallet/` | Organizer payout wallet | Organizer |
| `/admin/` | Django admin panel | Superuser |

---

## Project Structure

```
Event-Booking-System/
├── accounts/           # User auth, registration, login, profile
├── events/
│   ├── models.py       # Event, Booking, TicketType, CouponCode,
│   │                   #   OrganizerProfile, TeamMember, PayoutRequest
│   ├── views.py        # All views including dashboard, refunds, wallet
│   ├── admin.py        # Django admin with custom actions
│   ├── notifications.py# Email (Gmail) + WhatsApp Business API
│   ├── utils.py        # QR code generation, iCal export
│   ├── urls.py         # URL patterns
│   └── templates/
│       └── events/
│           ├── base.html            # Base layout + navbar + footer
│           ├── event_list.html      # Home page
│           ├── all_events.html      # Browse all events
│           ├── event_detail.html    # Event detail + booking sidebar
│           ├── payment_page.html    # Razorpay payment
│           ├── booking_success.html # Confirmation + QR
│           ├── my_bookings.html     # User bookings list
│           ├── ticket_download.html # Printable offline ticket
│           ├── dashboard.html       # Sales dashboard
│           ├── refund_management.html
│           ├── send_reminder.html
│           └── payout_wallet.html
├── media/              # QR code images
└── manage.py
```

---

## Booking Flow

1. Browse events → select event → choose ticket type (Normal / Premium / VIP)
2. Fill in attendee details and optional coupon code
3. Pay via Razorpay (card, UPI, net banking, wallet)
4. On payment confirmation: booking marked confirmed, QR code generated, email + WhatsApp sent
5. Download printable ticket or add event to calendar

---

## Technologies Used

| Layer | Technology |
|-------|-----------|
| Backend | Django 5.0.1 |
| Frontend | Bootstrap 5, Font Awesome 6, vanilla JS |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Payments | Razorpay |
| Maps | Leaflet.js + OpenStreetMap |
| QR Codes | `qrcode` library |
| Calendar | `icalendar` library |
| Notifications | Gmail SMTP + Meta WhatsApp Business API |

---

## Test Credentials (after running `seed_data`)

| Role | Username | Password |
|------|----------|----------|
| Admin / Staff | `admin` | `admin123` |
| User | `rahul_sharma` | `test1234` |
| User | `priya_patel` | `test1234` |

**Sample coupon codes:** `WELCOME20`, `FLAT500`, `TECH50`, `STUDENT15`

---

## Support

For technical support or feature requests, please contact:
- Email: contact@codeaj.com
- Phone: +918603862290

## Legal

This software is proprietary to CodeAJ Marketplace. See the LEGAL.md file for full terms and conditions.
