from django.urls import path
from . import views

urlpatterns = [
    # ── Public ───────────────────────────────────────────────────────────────
    path('', views.event_list, name='event_list'),
    path('events/', views.all_events, name='all_events'),
    path('event/<uuid:event_id>/', views.event_detail, name='event_detail'),

    # ── Booking flow (no login required) ─────────────────────────────────────
    path('payment/<uuid:booking_id>/', views.payment_page, name='payment_page'),
    path('payment-handler/', views.payment_handler, name='payment_handler'),
    path('booking/<uuid:booking_id>/success/', views.booking_success, name='booking_success'),
    path('booking/<uuid:booking_id>/failed/', views.payment_failed, name='payment_failed'),
    path('booking/<uuid:booking_id>/calendar/', views.download_calendar, name='download_calendar'),
    path('booking/<uuid:booking_id>/ticket/', views.download_ticket, name='download_ticket'),

    # ── My Tickets / Bookings ─────────────────────────────────────────────────
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('search-booking/', views.search_booking, name='search_booking'),

    # ── Coupon validation AJAX ────────────────────────────────────────────────
    path('validate-coupon/', views.validate_coupon, name='validate_coupon'),

    # ── Public Organizer Directory ────────────────────────────────────────────
    path('organizers/', views.organizer_list, name='organizer_list'),
    path('organizer/<str:username>/', views.organizer_detail, name='organizer_detail'),

    # ── QR Scanner (verifier / staff) ─────────────────────────────────────────
    path('scanner/', views.qr_scanner, name='qr_scanner'),
    path('verify-ticket/', views.verify_ticket, name='verify_ticket'),

    # ── Team Member Management ─────────────────────────────────────────────────
    path('team/', views.manage_team, name='manage_team'),

    # ── Staff / Admin views ───────────────────────────────────────────────────
    path('dashboard/', views.sales_dashboard, name='sales_dashboard'),
    path('refunds/', views.refund_management, name='refund_management'),
    path('event/<uuid:event_id>/export/', views.export_attendees_csv, name='export_attendees_csv'),
    path('event/<uuid:event_id>/import/', views.import_attendees, name='import_attendees'),
    path('event/<uuid:event_id>/send-reminder/', views.send_reminder, name='send_reminder'),
    path('event/<uuid:event_id>/complete/', views.complete_event_export, name='complete_event_export'),

    # ── Organizer wallet ──────────────────────────────────────────────────────
    path('wallet/', views.payout_wallet, name='payout_wallet'),

    # ── Dedicated Tickets Page ────────────────────────────────────────────────
    path('tickets/', views.my_tickets, name='my_tickets'),

    # ── Legal / Static pages (required for Razorpay verification) ────────────
    path('terms/', views.terms_view, name='terms'),
    path('privacy/', views.privacy_view, name='privacy'),
    path('refund-policy/', views.refund_policy_view, name='refund_policy'),
    path('shipping-policy/', views.shipping_policy_view, name='shipping_policy'),
    path('contact/', views.contact_view, name='contact'),
    path('about/', views.about_view, name='about'),
]
