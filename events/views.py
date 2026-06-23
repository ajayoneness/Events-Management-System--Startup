from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Count
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.urls import reverse
from django.contrib.auth.models import User
import razorpay
import json
import csv
import logging
from datetime import timedelta

from .models import (
    Event, Booking, SiteSettings, TicketType, CouponCode,
    OrganizerProfile, PayoutRequest, TeamMember, EventDataExport
)
from .forms import BookingForm
from .utils import generate_qr_code, generate_ical
from .notifications import send_booking_email, send_whatsapp_notification

logger = logging.getLogger(__name__)

_razorpay_client = None


def get_razorpay_client():
    global _razorpay_client
    try:
        cfg = SiteSettings.get_settings()
        key_id = cfg.razorpay_key_id or settings.RAZORPAY_KEY_ID
        key_secret = cfg.razorpay_key_secret or settings.RAZORPAY_KEY_SECRET
    except Exception:
        key_id = settings.RAZORPAY_KEY_ID
        key_secret = settings.RAZORPAY_KEY_SECRET
    return razorpay.Client(auth=(key_id, key_secret))


def is_authorized_for_booking(request, booking):
    """Check if the current request is authorized to view/access this booking."""
    if request.user.is_authenticated:
        if booking.user == request.user or request.user.is_staff:
            return True
    # Anonymous users: check session
    booking_ids = request.session.get('booking_ids', [])
    if str(booking.id) in booking_ids:
        return True
    # Allow if booking has no user and the session has a related email (search flow)
    return False


CATEGORY_META = {
    'music':    {'icon': 'fa-music',     'grad': 'linear-gradient(135deg,#EF4444,#DC2626)', 'light': '#FEF2F2', 'border': '#FECACA'},
    'tech':     {'icon': 'fa-microchip', 'grad': 'linear-gradient(135deg,#3B82F6,#1D4ED8)', 'light': '#EFF6FF', 'border': '#BFDBFE'},
    'sports':   {'icon': 'fa-futbol',    'grad': 'linear-gradient(135deg,#22C55E,#15803D)', 'light': '#F0FDF4', 'border': '#BBF7D0'},
    'food':     {'icon': 'fa-utensils',  'grad': 'linear-gradient(135deg,#F97316,#EA580C)', 'light': '#FFF7ED', 'border': '#FED7AA'},
    'art':      {'icon': 'fa-palette',   'grad': 'linear-gradient(135deg,#A855F7,#7C3AED)', 'light': '#FDF4FF', 'border': '#E9D5FF'},
    'business': {'icon': 'fa-briefcase', 'grad': 'linear-gradient(135deg,#0EA5E9,#0369A1)', 'light': '#F0F9FF', 'border': '#BAE6FD'},
    'other':    {'icon': 'fa-star',      'grad': 'linear-gradient(135deg,#6B7280,#374151)', 'light': '#F9FAFB', 'border': '#E5E7EB'},
}


@csrf_exempt
def validate_coupon(request):
    if request.method != 'POST':
        return JsonResponse({'valid': False, 'error': 'Invalid request'})
    code     = request.POST.get('code', '').strip().upper()
    amount   = float(request.POST.get('amount', 0) or 0)
    event_id = request.POST.get('event_id', '').strip()
    if not code:
        return JsonResponse({'valid': False, 'error': 'Please enter a coupon code'})
    try:
        coupon_qs = CouponCode.objects.filter(code=code, is_active=True)
        if event_id:
            coupon_qs = coupon_qs.filter(Q(event__id=event_id) | Q(event__isnull=True))
        coupon = coupon_qs.get()
    except CouponCode.DoesNotExist:
        return JsonResponse({'valid': False, 'error': 'Invalid or inactive coupon code'})
    now = timezone.now()
    if coupon.valid_from and coupon.valid_from > now:
        return JsonResponse({'valid': False, 'error': 'This coupon is not active yet'})
    if coupon.valid_until and coupon.valid_until < now:
        return JsonResponse({'valid': False, 'error': 'This coupon has expired'})
    if coupon.max_uses and coupon.used_count >= coupon.max_uses:
        return JsonResponse({'valid': False, 'error': 'This coupon has reached its usage limit'})
    if amount < float(coupon.minimum_amount):
        return JsonResponse({'valid': False, 'error': f'Minimum order of ₹{int(coupon.minimum_amount)} required'})
    if coupon.discount_type == 'percentage':
        discount = (amount * float(coupon.discount_value)) / 100
        label = f'{int(coupon.discount_value)}% off'
    else:
        discount = float(coupon.discount_value)
        label = f'₹{int(coupon.discount_value)} off'
    discount = min(discount, amount)
    return JsonResponse({
        'valid': True,
        'discount_type':   coupon.discount_type,
        'discount_value':  float(coupon.discount_value),
        'discount_amount': round(discount, 2),
        'final_amount':    round(amount - discount, 2),
        'message':         f'{label} applied! 🎉',
    })


def all_events(request):
    search_query      = request.GET.get('search', '').strip()
    selected_category = request.GET.get('category', '').strip()
    sort              = request.GET.get('sort', 'date')
    qs = Event.objects.filter(date__gte=timezone.now(), status='published', is_approved=True)
    if search_query:
        qs = qs.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query) | Q(venue__icontains=search_query))
    category_counts = {item['category']: item['count'] for item in qs.values('category').annotate(count=Count('id'))}
    total_count = qs.count()
    if selected_category:
        qs = qs.filter(category=selected_category)
    sort_map = {'price_asc': 'price', 'price_desc': '-price', 'newest': '-date', 'date': 'date'}
    qs = qs.order_by(sort_map.get(sort, 'date'))
    show_grouped = not selected_category and not search_query
    grouped_events = {}
    if show_grouped:
        for code, name in Event.CATEGORY_CHOICES:
            cat_qs = qs.filter(category=code)
            count = cat_qs.count()
            if count:
                meta = CATEGORY_META.get(code, CATEGORY_META['other'])
                grouped_events[code] = {
                    'name': name, 'events': list(cat_qs[:4]), 'total': count,
                    'icon': meta['icon'], 'grad': meta['grad'], 'light': meta['light'], 'border': meta['border'],
                }
        events = []
    else:
        events = list(qs)
    categories_with_counts = [
        (code, name, category_counts.get(code, 0))
        for code, name in Event.CATEGORY_CHOICES
        if category_counts.get(code, 0) > 0
    ]
    return render(request, 'events/all_events.html', {
        'events': events, 'grouped_events': grouped_events,
        'categories': Event.CATEGORY_CHOICES, 'categories_with_counts': categories_with_counts,
        'category_meta': CATEGORY_META, 'selected_category': selected_category,
        'search_query': search_query, 'sort': sort, 'total_count': total_count,
        'show_grouped': show_grouped,
    })


def event_list(request):
    events = Event.objects.filter(date__gte=timezone.now(), status='published', is_approved=True)
    search_query = request.GET.get('search', '')
    if search_query:
        events = events.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query) | Q(venue__icontains=search_query))
    category = request.GET.get('category', '')
    if category:
        events = events.filter(category=category)
    location = request.GET.get('location', '')
    if location:
        events = events.filter(address__icontains=location)
    return render(request, 'events/event_list.html', {
        'events': events, 'categories': Event.CATEGORY_CHOICES,
        'search_query': search_query, 'selected_category': category,
    })


def event_detail(request, event_id):
    """Event detail + booking form — no login required."""
    event = get_object_or_404(Event, id=event_id)
    ticket_types = event.ticket_types.filter(is_active=True)
    has_ticket_types = ticket_types.exists()

    if request.method == 'POST':
        form = BookingForm(request.POST)
        ticket_type = None
        ticket_type_id = request.POST.get('ticket_type_id', '').strip()

        if has_ticket_types:
            if not ticket_type_id:
                messages.error(request, 'Please select a ticket type before continuing.')
                return render(request, 'events/event_detail.html', {'event': event, 'form': form, 'ticket_types': ticket_types})
            try:
                ticket_type = ticket_types.get(id=ticket_type_id)
            except TicketType.DoesNotExist:
                messages.error(request, 'Invalid ticket type. Please try again.')
                return render(request, 'events/event_detail.html', {'event': event, 'form': form, 'ticket_types': ticket_types})

        if form.is_valid():
            booking = form.save(commit=False)
            booking.event = event
            booking.user = request.user if request.user.is_authenticated else None
            booking.status = 'pending'
            booking.ticket_type = ticket_type
            price_per_ticket = ticket_type.price if ticket_type else event.price
            booking.total_amount = price_per_ticket * booking.number_of_tickets

            coupon_code_str = request.POST.get('coupon_code', '').strip().upper()
            if coupon_code_str:
                try:
                    coupon_qs = CouponCode.objects.filter(code=coupon_code_str, is_active=True)
                    coupon_qs = coupon_qs.filter(Q(event=event) | Q(event__isnull=True))
                    coupon = coupon_qs.get()
                    now = timezone.now()
                    if (
                        (not coupon.valid_from or coupon.valid_from <= now) and
                        (not coupon.valid_until or coupon.valid_until >= now) and
                        (not coupon.max_uses or coupon.used_count < coupon.max_uses) and
                        booking.total_amount >= coupon.minimum_amount
                    ):
                        if coupon.discount_type == 'percentage':
                            discount = (booking.total_amount * coupon.discount_value) / 100
                        else:
                            discount = coupon.discount_value
                        discount = min(discount, booking.total_amount)
                        booking.discount_amount = discount
                        booking.total_amount = booking.total_amount - discount
                        booking.coupon_code = coupon
                except CouponCode.DoesNotExist:
                    pass

            available = ticket_type.available_seats if ticket_type else event.available_seats
            if available < booking.number_of_tickets:
                messages.error(request, f'Only {available} seat(s) left for this ticket type.')
                return render(request, 'events/event_detail.html', {'event': event, 'form': form, 'ticket_types': ticket_types})

            booking.save()

            # Always store booking in session (works for both anon and logged-in users)
            if 'booking_ids' not in request.session:
                request.session['booking_ids'] = []
            request.session['booking_ids'].append(str(booking.id))
            request.session.modified = True

            # Handle free events — confirm immediately
            if booking.total_amount == 0:
                booking.status = 'confirmed'
                booking.save()
                try:
                    generate_qr_code(booking)
                except Exception:
                    pass
                try:
                    send_booking_email(booking)
                except Exception:
                    pass
                messages.success(request, 'Your free ticket has been confirmed!')
                return redirect('booking_success', booking_id=booking.id)

            try:
                razorpay_order = get_razorpay_client().order.create({
                    'amount': int(booking.total_amount * 100),
                    'currency': 'INR',
                    'payment_capture': '1',
                    'notes': {
                        'booking_id': str(booking.id),
                        'event': event.title,
                        'ticket_type': ticket_type.name if ticket_type else 'General',
                    }
                })
                booking.razorpay_order_id = razorpay_order['id']
                booking.save()
                return redirect('payment_page', booking_id=booking.id)
            except Exception as e:
                logger.error(f"Razorpay order creation failed: {e}")
                messages.error(request, f'Payment setup failed: {e}')
                booking.delete()
    else:
        form = BookingForm()

    return render(request, 'events/event_detail.html', {
        'event': event, 'form': form, 'ticket_types': ticket_types,
    })


def payment_page(request, booking_id):
    """Razorpay payment page — no login required."""
    booking = get_object_or_404(Booking, id=booking_id)
    if not is_authorized_for_booking(request, booking):
        messages.error(request, "You don't have permission to access this booking.")
        return redirect('event_list')
    if booking.status == 'confirmed':
        return redirect('booking_success', booking_id=booking.id)
    try:
        cfg = SiteSettings.get_settings()
        razorpay_key = cfg.razorpay_key_id or settings.RAZORPAY_KEY_ID
    except Exception:
        razorpay_key = settings.RAZORPAY_KEY_ID
    callback_url = request.build_absolute_uri(reverse('payment_handler'))
    return render(request, 'events/payment_page.html', {
        'booking': booking,
        'razorpay_key_id': razorpay_key,
        'razorpay_order_id': booking.razorpay_order_id,
        'amount': int(booking.total_amount * 100),
        'currency': 'INR',
        'callback_url': callback_url,
        'is_test_mode': razorpay_key.startswith('rzp_test_'),
    })


@csrf_exempt
def payment_handler(request):
    """Handle Razorpay payment callback."""
    if request.method not in ('GET', 'POST'):
        return redirect('event_list')
    data = request.POST if request.method == 'POST' else request.GET
    try:
        payment_id        = data.get('razorpay_payment_id', '').strip()
        razorpay_order_id = data.get('razorpay_order_id', '').strip()
        signature         = data.get('razorpay_signature', '').strip()
        logger.info(f"Payment handler called for order: {razorpay_order_id}")
        if not all([payment_id, razorpay_order_id, signature]):
            messages.error(request, 'Invalid payment details received.')
            return redirect('event_list')
        try:
            booking = Booking.objects.get(razorpay_order_id=razorpay_order_id)
        except Booking.DoesNotExist:
            messages.error(request, 'Booking not found.')
            return redirect('event_list')
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature,
        }
        try:
            get_razorpay_client().utility.verify_payment_signature(params_dict)
            booking.razorpay_payment_id = payment_id
            booking.razorpay_signature  = signature
            booking.status = 'confirmed'
            booking.save()
            event = booking.event
            event.available_seats -= booking.number_of_tickets
            event.save()
            if booking.ticket_type:
                booking.ticket_type.available_seats -= booking.number_of_tickets
                booking.ticket_type.save()
            if booking.coupon_code_id:
                CouponCode.objects.filter(pk=booking.coupon_code_id).update(
                    used_count=booking.coupon_code.used_count + 1
                )
            try:
                generate_qr_code(booking)
            except Exception as e:
                logger.error(f"QR code generation failed: {e}")
            try:
                if send_booking_email(booking):
                    booking.email_sent = True
                    booking.save(update_fields=['email_sent'])
            except Exception as e:
                logger.error(f"Email notification failed: {e}")
            try:
                if send_whatsapp_notification(booking):
                    booking.whatsapp_sent = True
                    booking.save(update_fields=['whatsapp_sent'])
            except Exception as e:
                logger.error(f"WhatsApp notification failed: {e}")
            messages.success(request, 'Payment successful! Your booking is confirmed.')
            return redirect('booking_success', booking_id=booking.id)
        except razorpay.errors.SignatureVerificationError as e:
            logger.error(f"Signature verification failed: {e}")
            booking.razorpay_payment_id = payment_id
            booking.status = 'failed'
            booking.save()
            messages.error(request, 'Payment verification failed! If money was deducted, it will be refunded within 5-7 business days.')
            return redirect('payment_failed', booking_id=booking.id)
    except Exception as e:
        logger.error(f"Payment handler error: {e}")
        messages.error(request, f'Payment processing error: {e}')
        return redirect('event_list')


def payment_failed(request, booking_id):
    """Payment failed page — no login required."""
    booking = get_object_or_404(Booking, id=booking_id)
    if not is_authorized_for_booking(request, booking):
        return redirect('event_list')
    if booking.status != 'failed':
        booking.status = 'failed'
        booking.save()
    return render(request, 'events/payment_failed.html', {'booking': booking})


def booking_success(request, booking_id):
    """Booking confirmation — no login required."""
    booking = get_object_or_404(Booking, id=booking_id)
    if not is_authorized_for_booking(request, booking):
        messages.error(request, "You don't have permission to access this booking.")
        return redirect('event_list')
    if booking.status != 'confirmed':
        messages.warning(request, 'This booking is not confirmed yet.')
        if booking.status == 'pending':
            return redirect('payment_page', booking_id=booking.id)
        return redirect('event_list')
    return render(request, 'events/booking_success.html', {'booking': booking})


def download_calendar(request, booking_id):
    """Download iCal file — no login required."""
    booking = get_object_or_404(Booking, id=booking_id)
    if not is_authorized_for_booking(request, booking):
        return redirect('event_list')
    ical_data = generate_ical(booking)
    response = HttpResponse(ical_data, content_type='text/calendar')
    response['Content-Disposition'] = f'attachment; filename="event_{booking.event.id}.ics"'
    return response


def my_bookings(request):
    """My Tickets/Bookings page — works for both logged-in and anonymous users."""
    bookings = []
    search_email = None

    if request.user.is_authenticated:
        bookings = Booking.objects.filter(user=request.user).order_by('-booking_date')
    else:
        # Show bookings stored in session
        session_ids = request.session.get('booking_ids', [])
        if session_ids:
            bookings = Booking.objects.filter(id__in=session_ids).order_by('-booking_date')

    return render(request, 'events/my_bookings.html', {
        'bookings': bookings,
        'search_email': search_email,
    })


def search_booking(request):
    """Search booking by email for anonymous users."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        booking_id = request.POST.get('booking_id', '').strip()
        if email:
            bookings = Booking.objects.filter(email=email).order_by('-booking_date')
            if booking_id:
                bookings = bookings.filter(id=booking_id)
            return render(request, 'events/my_bookings.html', {
                'bookings': bookings, 'search_email': email,
            })
        messages.error(request, 'Please enter your email address.')
    return render(request, 'events/search_booking.html')


def download_ticket(request, booking_id):
    """Printable ticket — no login required."""
    booking = get_object_or_404(Booking, id=booking_id)
    if not is_authorized_for_booking(request, booking):
        if request.user.is_staff:
            pass
        else:
            messages.error(request, 'Access denied.')
            return redirect('event_list')
    if booking.status != 'confirmed':
        messages.error(request, 'Ticket is only available for confirmed bookings.')
        return redirect('my_bookings')
    return render(request, 'events/ticket_download.html', {'booking': booking})


# ─────────────────────────────────────────────────────────────────────────────
# ORGANIZER PUBLIC DIRECTORY
# ─────────────────────────────────────────────────────────────────────────────

def organizer_list(request):
    """Public directory of event organizers."""
    organizers = OrganizerProfile.objects.filter(
        status='verified', is_public=True
    ).select_related('user').order_by('organization_name')
    search = request.GET.get('q', '').strip()
    if search:
        organizers = organizers.filter(
            Q(organization_name__icontains=search) |
            Q(user__username__icontains=search) |
            Q(description__icontains=search)
        )
    # Annotate with event counts
    for org in organizers:
        org.event_count = Event.objects.filter(
            organizer_user=org.user, status='published', is_approved=True
        ).count()
    return render(request, 'events/organizer_list.html', {
        'organizers': organizers, 'search': search,
    })


def organizer_detail(request, username):
    """Public organizer profile page with their events."""
    user = get_object_or_404(User, username=username)
    try:
        organizer = user.organizer_profile
    except OrganizerProfile.DoesNotExist:
        messages.error(request, 'Organizer profile not found.')
        return redirect('organizer_list')
    if not organizer.is_public and not request.user.is_staff:
        messages.error(request, 'This organizer profile is private.')
        return redirect('organizer_list')
    events = Event.objects.filter(
        organizer_user=user, status='published', is_approved=True
    ).order_by('date')
    past_events = Event.objects.filter(
        organizer_user=user, status='completed'
    ).order_by('-date')[:6]
    return render(request, 'events/organizer_detail.html', {
        'organizer': organizer, 'events': events, 'past_events': past_events,
    })


# ─────────────────────────────────────────────────────────────────────────────
# QR SCANNER (team member verifier)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def qr_scanner(request):
    """QR code scanner page for ticket verifiers."""
    # Allow staff or team members with verifier role
    is_verifier = False
    try:
        member = request.user.team_member_profile
        if member.role == 'verifier' and member.is_active:
            is_verifier = True
    except Exception:
        pass

    if not is_verifier and not request.user.is_staff:
        messages.error(request, 'Access denied. This page is for ticket verifiers only.')
        return redirect('event_list')

    # Get events the verifier is assigned to (for staff: all events)
    if request.user.is_staff:
        events = Event.objects.filter(status='published').order_by('-date')
    else:
        organizer = request.user.team_member_profile.organizer
        events = Event.objects.filter(organizer_user=organizer, status='published').order_by('-date')

    return render(request, 'events/qr_scanner.html', {
        'events': events,
        'is_verifier': is_verifier,
    })


@csrf_exempt
@login_required
def verify_ticket(request):
    """AJAX endpoint — verify a booking QR code."""
    if request.method != 'POST':
        return JsonResponse({'valid': False, 'error': 'Invalid request'})

    booking_id = request.POST.get('booking_id', '').strip()
    if not booking_id:
        return JsonResponse({'valid': False, 'error': 'No booking ID provided'})

    try:
        booking = Booking.objects.select_related('event', 'ticket_type').get(id=booking_id)
    except (Booking.DoesNotExist, Exception):
        # Fallback: short 8-char prefix match (e.g. "EBB1106C" typed manually)
        short = booking_id.lower().replace('-', '')
        booking = None
        if len(short) >= 4:
            for b in Booking.objects.select_related('event', 'ticket_type').all():
                if str(b.id).replace('-', '').startswith(short):
                    booking = b
                    break
        if booking is None:
            return JsonResponse({'valid': False, 'error': 'Booking not found', 'color': 'red'})

    if booking.status == 'confirmed':
        # Increment scan count atomically
        Booking.objects.filter(pk=booking.pk).update(scan_count=booking.scan_count + 1)
        new_count = booking.scan_count + 1
        already_scanned = new_count > 1
        return JsonResponse({
            'valid': True,
            'already_scanned': already_scanned,
            'scan_count': new_count,
            'color': 'orange' if already_scanned else 'green',
            'name': booking.name,
            'event': booking.event.title,
            'ticket_type': booking.ticket_type.name if booking.ticket_type else 'Standard',
            'tickets': booking.number_of_tickets,
            'booking_id': str(booking.id)[:8].upper(),
            'message': f'⚠️ ALREADY SCANNED {new_count} TIME{"S" if new_count != 1 else ""}' if already_scanned else 'VALID TICKET ✓',
        })
    else:
        status_msg = {
            'pending': 'Payment pending — ticket not confirmed',
            'cancelled': 'Ticket cancelled',
            'refunded': 'Ticket refunded',
            'failed': 'Payment failed',
        }.get(booking.status, f'Invalid status: {booking.status}')
        return JsonResponse({
            'valid': False,
            'color': 'red',
            'name': booking.name,
            'message': status_msg,
        })


# ─────────────────────────────────────────────────────────────────────────────
# IMPORT ATTENDEES (organizer / staff)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def import_attendees(request, event_id):
    """Import attendees from CSV and optionally send tickets via email/WhatsApp."""
    if not request.user.is_staff:
        # Check if user is the event organizer
        event_check = get_object_or_404(Event, id=event_id)
        if event_check.organizer_user != request.user:
            messages.error(request, 'Access denied.')
            return redirect('event_list')

    event = get_object_or_404(Event, id=event_id)

    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        send_email = request.POST.get('send_email') == 'on'
        send_whatsapp = request.POST.get('send_whatsapp') == 'on'

        try:
            decoded = csv_file.read().decode('utf-8-sig')
            reader = csv.DictReader(decoded.splitlines())
            created, failed, skipped = 0, 0, 0

            for row in reader:
                try:
                    name  = (row.get('Name') or row.get('name') or '').strip()
                    email = (row.get('Email') or row.get('email') or '').strip().lower()
                    phone = (row.get('Phone') or row.get('phone') or row.get('Mobile') or '').strip()
                    ticket_name = (row.get('Ticket Type') or row.get('ticket_type') or '').strip()
                    qty = int(row.get('Tickets') or row.get('quantity') or row.get('qty') or 1)

                    if not name or not email:
                        skipped += 1
                        continue

                    # Check for duplicate
                    if Booking.objects.filter(event=event, email=email).exists():
                        skipped += 1
                        continue

                    ticket_type = None
                    if ticket_name:
                        try:
                            ticket_type = event.ticket_types.get(name__iexact=ticket_name)
                        except TicketType.DoesNotExist:
                            pass

                    price = ticket_type.price if ticket_type else event.price
                    total = price * qty

                    booking = Booking.objects.create(
                        event=event,
                        name=name,
                        email=email,
                        phone=phone,
                        ticket_type=ticket_type,
                        number_of_tickets=qty,
                        total_amount=total,
                        status='confirmed',
                        is_manual=True,
                    )

                    try:
                        generate_qr_code(booking)
                    except Exception:
                        pass

                    if send_email:
                        try:
                            send_booking_email(booking)
                            booking.email_sent = True
                            booking.save(update_fields=['email_sent'])
                        except Exception:
                            pass

                    if send_whatsapp:
                        try:
                            send_whatsapp_notification(booking)
                            booking.whatsapp_sent = True
                            booking.save(update_fields=['whatsapp_sent'])
                        except Exception:
                            pass

                    created += 1
                except Exception as row_err:
                    logger.error(f"CSV import row error: {row_err}")
                    failed += 1

            messages.success(request, f'Import complete: {created} created, {skipped} skipped (duplicate/missing), {failed} failed.')
        except Exception as e:
            messages.error(request, f'CSV parsing error: {e}')

        return redirect('import_attendees', event_id=event_id)

    return render(request, 'events/import_attendees.html', {'event': event})


# ─────────────────────────────────────────────────────────────────────────────
# SALES DASHBOARD (staff only)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def sales_dashboard(request):
    if not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('event_list')

    total_revenue = Booking.objects.filter(status='confirmed').aggregate(total=Sum('total_amount'))['total'] or 0
    total_bookings   = Booking.objects.count()
    confirmed_count  = Booking.objects.filter(status='confirmed').count()
    pending_count    = Booking.objects.filter(status='pending').count()
    refund_count     = Booking.objects.filter(status='refunded').count()
    total_events     = Event.objects.filter(status='published').count()

    top_events = (
        Booking.objects.filter(status='confirmed')
        .values('event__title', 'event__id')
        .annotate(revenue=Sum('total_amount'), bookings=Count('id'))
        .order_by('-revenue')[:5]
    )
    status_breakdown = {
        'confirmed': confirmed_count, 'pending': pending_count,
        'refunded': refund_count,
        'cancelled': Booking.objects.filter(status='cancelled').count(),
        'failed': Booking.objects.filter(status='failed').count(),
    }
    recent_bookings = Booking.objects.select_related('event').order_by('-booking_date')[:15]
    all_events      = Event.objects.order_by('-created_at')[:30]
    pending_payouts = PayoutRequest.objects.filter(status='pending').count()

    # Organizer stats for main admin
    organizer_stats = (
        OrganizerProfile.objects.select_related('user')
        .annotate(
            event_count=Count('user__organized_events', distinct=True),
        )
        .order_by('-wallet_balance')[:20]
    )
    # Add revenue per organizer
    for org in organizer_stats:
        org.total_revenue = Booking.objects.filter(
            event__organizer_user=org.user, status='confirmed'
        ).aggregate(total=Sum('total_amount'))['total'] or 0

    pending_organizers = OrganizerProfile.objects.filter(status='pending').count()

    return render(request, 'events/dashboard.html', {
        'total_revenue': total_revenue, 'total_bookings': total_bookings,
        'confirmed_count': confirmed_count, 'pending_count': pending_count,
        'refund_count': refund_count, 'total_events': total_events,
        'top_events': top_events, 'status_breakdown': status_breakdown,
        'recent_bookings': recent_bookings, 'all_events': all_events,
        'pending_payouts': pending_payouts, 'organizer_stats': organizer_stats,
        'pending_organizers': pending_organizers,
    })


# ─────────────────────────────────────────────────────────────────────────────
# EXPORT ATTENDEES CSV (staff only)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def export_attendees_csv(request, event_id):
    if not request.user.is_staff and not _get_org_profile(request.user):
        messages.error(request, 'Access denied.')
        return redirect('event_list')
    if request.user.is_staff:
        event = get_object_or_404(Event, id=event_id)
    else:
        event = get_object_or_404(Event, id=event_id, organizer_user=request.user)
    status   = request.GET.get('status', 'confirmed')
    bookings = Booking.objects.filter(event=event)
    if status != 'all':
        bookings = bookings.filter(status=status)
    response = HttpResponse(content_type='text/csv')
    safe_title = event.title[:40].replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="attendees_{safe_title}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Email', 'Phone', 'Ticket Type', 'No. of Tickets', 'Amount (₹)', 'Discount (₹)', 'Coupon Code', 'Status', 'Booking Date', 'Payment ID', 'Manual'])
    for b in bookings:
        writer.writerow([
            b.name, b.email, b.phone,
            b.ticket_type.name if b.ticket_type else 'Standard',
            b.number_of_tickets, b.total_amount, b.discount_amount,
            b.coupon_code.code if b.coupon_code else '',
            b.get_status_display(), b.booking_date.strftime('%Y-%m-%d %H:%M'),
            b.razorpay_payment_id or '',
            'Yes' if b.is_manual else 'No',
        ])
    return response


# ─────────────────────────────────────────────────────────────────────────────
# COMPLETED EVENT DATA EXPORT + 90-DAY SCHEDULE (staff only)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def complete_event_export(request, event_id):
    """Mark event as completed, export data, schedule 90-day deletion."""
    if not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('event_list')

    event = get_object_or_404(Event, id=event_id)

    if request.method == 'POST':
        send_to_email = request.POST.get('send_to_email', '').strip()

        # Mark event completed
        event.status = 'completed'
        event.save(update_fields=['status'])

        # Build CSV
        import io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['Name', 'Email', 'Phone', 'Ticket Type', 'Tickets', 'Amount', 'Status', 'Booking Date', 'Payment ID'])
        for b in Booking.objects.filter(event=event, status='confirmed'):
            writer.writerow([
                b.name, b.email, b.phone,
                b.ticket_type.name if b.ticket_type else 'Standard',
                b.number_of_tickets, b.total_amount,
                b.get_status_display(), b.booking_date.strftime('%Y-%m-%d %H:%M'),
                b.razorpay_payment_id or '',
            ])
        csv_data = buffer.getvalue()

        # Schedule deletion in 90 days
        delete_at = timezone.now() + timedelta(days=90)
        export = EventDataExport.objects.create(
            event=event,
            scheduled_delete_at=delete_at,
            sent_to_email=send_to_email,
        )

        # Send via email if address provided
        if send_to_email:
            try:
                from .notifications import send_event_export_email
                send_event_export_email(event, csv_data, send_to_email)
                export.email_sent = True
                export.save(update_fields=['email_sent'])
            except Exception as e:
                logger.error(f"Event export email failed: {e}")

        messages.success(request, f'Event "{event.title}" marked as completed. Data export scheduled for deletion on {delete_at.strftime("%Y-%m-%d")}.')
        return redirect('sales_dashboard')

    confirmed_count = Booking.objects.filter(event=event, status='confirmed').count()
    return render(request, 'events/complete_event.html', {
        'event': event, 'confirmed_count': confirmed_count,
    })


# ─────────────────────────────────────────────────────────────────────────────
# REFUND MANAGEMENT (staff only)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def refund_management(request):
    if not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('event_list')
    if request.method == 'POST':
        booking_id = request.POST.get('booking_id', '').strip()
        action     = request.POST.get('action', '').strip()
        reason     = request.POST.get('reason', '').strip()
        try:
            booking = Booking.objects.get(id=booking_id)
            if action == 'refund':
                booking.status       = 'refunded'
                booking.refunded_at  = timezone.now()
                booking.refund_reason = reason or 'Refunded by admin'
                booking.save()
                booking.event.available_seats += booking.number_of_tickets
                booking.event.save(update_fields=['available_seats'])
                if booking.ticket_type:
                    booking.ticket_type.available_seats += booking.number_of_tickets
                    booking.ticket_type.save(update_fields=['available_seats'])
                messages.success(request, f'Booking by {booking.name} marked as refunded.')
            elif action == 'cancel':
                booking.status = 'cancelled'
                booking.save()
                messages.success(request, f'Booking by {booking.name} cancelled.')
        except Booking.DoesNotExist:
            messages.error(request, 'Booking not found.')
        return redirect('refund_management')
    status_filter = request.GET.get('status', 'confirmed')
    qs = Booking.objects.select_related('event').order_by('-booking_date')
    if status_filter and status_filter != 'all':
        qs = qs.filter(status=status_filter)
    return render(request, 'events/refund_management.html', {
        'bookings': qs[:60], 'status_filter': status_filter,
    })


# ─────────────────────────────────────────────────────────────────────────────
# SEND EMAIL REMINDER (staff only)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def send_reminder(request, event_id):
    if not request.user.is_staff and not _get_org_profile(request.user):
        messages.error(request, 'Access denied.')
        return redirect('event_list')
    if request.user.is_staff:
        event = get_object_or_404(Event, id=event_id)
    else:
        event = get_object_or_404(Event, id=event_id, organizer_user=request.user)
    if request.method == 'POST':
        reminder_type = request.POST.get('reminder_type', 'normal')
        bookings = Booking.objects.filter(event=event, status='confirmed')
        sent, failed = 0, 0
        for b in bookings:
            try:
                if send_booking_email(b):
                    sent += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
        # Get cost from settings
        try:
            cfg = SiteSettings.get_settings()
            cost = float(cfg.reminder_normal_cost if reminder_type == 'normal' else cfg.reminder_advance_cost)
            total_cost = cost * sent
        except Exception:
            total_cost = 0
        messages.success(request, f'Reminder sent to {sent} attendee(s). {failed} failed. Total cost: ₹{total_cost:.0f}.')
        return redirect('sales_dashboard')
    attendee_count = Booking.objects.filter(event=event, status='confirmed').count()
    try:
        cfg = SiteSettings.get_settings()
        normal_cost = float(cfg.reminder_normal_cost)
        advance_cost = float(cfg.reminder_advance_cost)
    except Exception:
        normal_cost, advance_cost = 5, 20
    return render(request, 'events/send_reminder.html', {
        'event': event, 'attendee_count': attendee_count,
        'normal_cost': normal_cost, 'advance_cost': advance_cost,
        'normal_total': normal_cost * attendee_count,
        'advance_total': advance_cost * attendee_count,
    })


# ─────────────────────────────────────────────────────────────────────────────
# PAYOUT WALLET (organizer)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def payout_wallet(request):
    try:
        organizer = request.user.organizer_profile
    except OrganizerProfile.DoesNotExist:
        messages.error(request, 'You need an organizer profile to access the wallet.')
        return redirect('event_list')

    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount', 0) or 0)
        except ValueError:
            amount = 0
        if amount <= 0:
            messages.error(request, 'Please enter a valid amount.')
        elif amount > float(organizer.wallet_balance):
            messages.error(request, f'Insufficient balance. Available: ₹{organizer.wallet_balance}')
        else:
            # Calculate payout charges
            try:
                cfg = SiteSettings.get_settings()
                charge_pct = float(cfg.payout_charge_percent)
            except Exception:
                charge_pct = 0
            charge = round(amount * charge_pct / 100, 2)
            net    = amount - charge
            PayoutRequest.objects.create(
                organizer_profile=organizer,
                amount=amount,
                note=request.POST.get('note', '').strip(),
            )
            messages.success(request, f'Payout request of ₹{amount:.0f} submitted! Processing charge: ₹{charge:.2f}. Net payout: ₹{net:.2f}. Admin will process it within 2-3 business days.')
        return redirect('payout_wallet')

    payout_requests = organizer.payout_requests.order_by('-created_at')[:20]
    total_paid = organizer.payout_requests.filter(status='paid').aggregate(total=Sum('amount'))['total'] or 0
    try:
        cfg = SiteSettings.get_settings()
        payout_charge_percent = float(cfg.payout_charge_percent)
    except Exception:
        payout_charge_percent = 0
    return render(request, 'events/payout_wallet.html', {
        'organizer': organizer,
        'payout_requests': payout_requests,
        'total_paid': total_paid,
        'payout_charge_percent': payout_charge_percent,
    })


# ─────────────────────────────────────────────────────────────────────────────
# ORGANIZER TEAM MEMBER MANAGEMENT (organizer / staff)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def manage_team(request):
    """Organizer team member management — create login accounts for team members."""
    if not request.user.is_staff:
        try:
            organizer = request.user.organizer_profile
        except OrganizerProfile.DoesNotExist:
            messages.error(request, 'Access denied.')
            return redirect('event_list')

    if request.user.is_staff:
        organizer_filter = request.GET.get('organizer')
        if organizer_filter:
            team_members = TeamMember.objects.filter(organizer__username=organizer_filter)
        else:
            team_members = TeamMember.objects.all().select_related('organizer', 'user')
    else:
        team_members = TeamMember.objects.filter(organizer=request.user).select_related('user')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_member':
            name  = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip().lower()
            phone = request.POST.get('phone', '').strip()
            role  = request.POST.get('role', 'verifier')

            if not name or not email:
                messages.error(request, 'Name and email are required.')
            else:
                # Create Django User account for team member
                # Generate username from name (more intuitive), fallback to email prefix
                import re
                base_username = re.sub(r'[^a-z0-9]', '', name.lower())[:15] or re.sub(r'[^a-z0-9]', '', email.split('@')[0])[:15] or 'member'
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1

                temp_password = get_random_string(length=10)
                member_user = User.objects.create_user(
                    username=username, email=email, password=temp_password,
                    first_name=name,
                )
                # Staff can specify an organizer via POST, otherwise defaults to self
                organizer_username = request.POST.get('organizer_username', '').strip()
                if request.user.is_staff and organizer_username:
                    organizer_user = User.objects.filter(username=organizer_username).first() or request.user
                else:
                    organizer_user = request.user

                member = TeamMember.objects.create(
                    organizer=organizer_user,
                    user=member_user,
                    name=name,
                    email=email,
                    phone=phone,
                    role=role,
                )
                messages.success(request, f'Team member "{name}" added. Login username: {username} | Temporary password: {temp_password}')

        elif action == 'deactivate':
            member_id = request.POST.get('member_id')
            qs = TeamMember.objects.filter(id=member_id)
            if not request.user.is_staff:
                qs = qs.filter(organizer=request.user)
            qs.update(is_active=False)
            messages.success(request, 'Team member deactivated.')

        elif action == 'reset_password':
            member_id = request.POST.get('member_id')
            qs = TeamMember.objects.filter(id=member_id).select_related('user')
            if not request.user.is_staff:
                qs = qs.filter(organizer=request.user)
            member = qs.first()
            if member and member.user:
                new_password = get_random_string(length=10)
                member.user.set_password(new_password)
                member.user.save()
                messages.success(request, f'Password reset for "{member.name}". New password: {new_password} | Username: {member.user.username}')
            else:
                messages.error(request, 'Member not found.')

        return redirect('manage_team')

    return render(request, 'events/manage_team.html', {'team_members': team_members})


# ─────────────────────────────────────────────────────────────────────────────
# STATIC / LEGAL PAGES  (required for Razorpay account verification)
# ─────────────────────────────────────────────────────────────────────────────

def terms_view(request):
    return render(request, 'events/terms.html')


def privacy_view(request):
    return render(request, 'events/privacy.html')


def refund_policy_view(request):
    return render(request, 'events/refund_policy.html')


def shipping_policy_view(request):
    return render(request, 'events/shipping_policy.html')


def contact_view(request):
    return render(request, 'events/contact.html')


def about_view(request):
    return render(request, 'events/about.html')


def organizer_agreement_view(request):
    return render(request, 'events/organizer_agreement.html')


# ─────────────────────────────────────────────────────────────────────────────
# DEDICATED TICKETS PAGE  (ticket wallet for logged-in users)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def my_tickets(request):
    """Ticket wallet — shows all confirmed tickets for the logged-in user."""
    all_bookings = Booking.objects.filter(user=request.user).select_related('event', 'ticket_type').order_by('-booking_date')
    confirmed = all_bookings.filter(status='confirmed')
    upcoming  = confirmed.filter(event__date__gte=timezone.now())
    past      = confirmed.filter(event__date__lt=timezone.now())
    pending   = all_bookings.filter(status='pending')
    context = {
        'upcoming_tickets': upcoming,
        'past_tickets': past,
        'pending_bookings': pending,
        'total_confirmed': confirmed.count(),
    }
    return render(request, 'events/my_tickets.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# ORGANISATION DASHBOARD  (for verified / unverified organisers)
# ─────────────────────────────────────────────────────────────────────────────

def _get_org_profile(user):
    """Return OrganizerProfile for user or None."""
    try:
        return user.organizer_profile
    except OrganizerProfile.DoesNotExist:
        return None


@login_required
def org_dashboard(request):
    """Organisation dashboard — shows own sales, events, team, etc."""
    profile = _get_org_profile(request.user)
    if not profile:
        messages.error(request, 'You do not have an organiser account.')
        return redirect('event_list')

    # ── Unverified state ──────────────────────────────────────────────
    if profile.status != 'verified':
        return render(request, 'events/org_dashboard_unverified.html', {
            'profile': profile,
        })

    # ── Verified: full dashboard ──────────────────────────────────────
    user = request.user
    my_events = Event.objects.filter(organizer_user=user).order_by('-created_at')
    my_bookings = Booking.objects.filter(event__organizer_user=user).select_related('event', 'ticket_type')

    total_revenue = my_bookings.filter(status='confirmed').aggregate(t=Sum('total_amount'))['t'] or 0
    confirmed_count = my_bookings.filter(status='confirmed').count()
    pending_count = my_bookings.filter(status='pending').count()
    refund_count = my_bookings.filter(status='refunded').count()
    total_tickets_sold = my_bookings.filter(status='confirmed').aggregate(t=Sum('number_of_tickets'))['t'] or 0

    top_events = (
        my_bookings.filter(status='confirmed')
        .values('event__title', 'event__id')
        .annotate(revenue=Sum('total_amount'), bookings=Count('id'))
        .order_by('-revenue')[:5]
    )
    recent_bookings = my_bookings.order_by('-booking_date')[:15]

    status_breakdown = {
        'confirmed': confirmed_count, 'pending': pending_count,
        'refunded': refund_count,
        'cancelled': my_bookings.filter(status='cancelled').count(),
        'failed': my_bookings.filter(status='failed').count(),
    }

    team_members = TeamMember.objects.filter(organizer=user)

    return render(request, 'events/org_dashboard.html', {
        'profile': profile,
        'my_events': my_events,
        'total_revenue': total_revenue,
        'confirmed_count': confirmed_count,
        'pending_count': pending_count,
        'refund_count': refund_count,
        'total_tickets_sold': total_tickets_sold,
        'total_events': my_events.count(),
        'published_events': my_events.filter(status='published', is_approved=True).count(),
        'pending_approval': my_events.filter(is_approved=False).count(),
        'top_events': top_events,
        'recent_bookings': recent_bookings,
        'status_breakdown': status_breakdown,
        'team_members': team_members,
    })


# ─────────────────────────────────────────────────────────────────────────────
# ORG ADD / EDIT EVENT
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def org_add_event(request):
    """Organiser creates a new event — starts with is_approved=False."""
    profile = _get_org_profile(request.user)
    if not profile or profile.status != 'verified':
        messages.error(request, 'Your organisation must be verified to create events.')
        return redirect('org_dashboard')

    if request.method == 'POST':
        try:
            from decimal import Decimal
            title = request.POST.get('title', '').strip()
            description = request.POST.get('description', '').strip()
            category = request.POST.get('category', 'other')
            event_type = request.POST.get('event_type', 'one_time')
            is_free = request.POST.get('is_free') == 'on'
            date_str = request.POST.get('date', '')
            end_date_str = request.POST.get('end_date', '')
            venue = request.POST.get('venue', '').strip()
            address = request.POST.get('address', '').strip()
            latitude = float(request.POST.get('latitude', '20.5937') or '20.5937')
            longitude = float(request.POST.get('longitude', '78.9629') or '78.9629')
            price = Decimal(request.POST.get('price', '0') or '0')
            total_seats = int(request.POST.get('total_seats', '100') or '100')
            image = request.POST.get('image', '').strip()

            if not title or not description or not date_str or not venue or not address:
                messages.error(request, 'Please fill all required fields.')
                return render(request, 'events/org_add_event.html', {
                    'profile': profile, 'form_data': request.POST, 'editing': False,
                })

            from django.utils.dateparse import parse_datetime
            event_date = parse_datetime(date_str)
            if not event_date:
                from datetime import datetime
                event_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
                from django.utils import timezone as tz
                event_date = tz.make_aware(event_date)

            end_date = None
            if end_date_str:
                end_date = parse_datetime(end_date_str)
                if not end_date:
                    from datetime import datetime
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M')
                    from django.utils import timezone as tz
                    end_date = tz.make_aware(end_date)

            event = Event.objects.create(
                title=title,
                description=description,
                category=category,
                event_type=event_type,
                is_free=is_free,
                status='published',
                is_approved=False,  # Needs admin approval
                date=event_date,
                end_date=end_date,
                venue=venue,
                address=address,
                latitude=latitude,
                longitude=longitude,
                price=price if not is_free else 0,
                total_seats=total_seats,
                available_seats=total_seats,
                image=image or 'https://via.placeholder.com/800x400/7C3AED/ffffff?text=Event+Image',
                organizer=profile.organization_name or request.user.get_full_name() or request.user.username,
                organizer_user=request.user,
            )

            # Create ticket types if provided
            ticket_names = request.POST.getlist('ticket_name')
            ticket_prices = request.POST.getlist('ticket_price')
            ticket_seats = request.POST.getlist('ticket_seats')
            ticket_tiers = request.POST.getlist('ticket_tier')
            for i in range(len(ticket_names)):
                if ticket_names[i].strip():
                    TicketType.objects.create(
                        event=event,
                        name=ticket_names[i].strip(),
                        tier=ticket_tiers[i] if i < len(ticket_tiers) else 'normal',
                        price=Decimal(ticket_prices[i]) if i < len(ticket_prices) and ticket_prices[i] else price,
                        total_seats=int(ticket_seats[i]) if i < len(ticket_seats) and ticket_seats[i] else total_seats,
                        available_seats=int(ticket_seats[i]) if i < len(ticket_seats) and ticket_seats[i] else total_seats,
                    )

            messages.success(request, f"Event '{title}' created! It will be visible on the website after admin approval.")
            return redirect('org_dashboard')
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            messages.error(request, f'Error creating event: {e}')
            return render(request, 'events/org_add_event.html', {
                'profile': profile, 'form_data': request.POST, 'editing': False,
            })

    return render(request, 'events/org_add_event.html', {
        'profile': profile, 'editing': False,
    })


@login_required
def org_edit_event(request, event_id):
    """Organiser edits their own event."""
    profile = _get_org_profile(request.user)
    if not profile or profile.status != 'verified':
        messages.error(request, 'Access denied.')
        return redirect('org_dashboard')

    event = get_object_or_404(Event, id=event_id, organizer_user=request.user)

    if request.method == 'POST':
        try:
            from decimal import Decimal
            event.title = request.POST.get('title', event.title).strip()
            event.description = request.POST.get('description', event.description).strip()
            event.category = request.POST.get('category', event.category)
            event.event_type = request.POST.get('event_type', event.event_type)
            event.is_free = request.POST.get('is_free') == 'on'
            event.venue = request.POST.get('venue', event.venue).strip()
            event.address = request.POST.get('address', event.address).strip()
            event.latitude = float(request.POST.get('latitude', event.latitude) or event.latitude)
            event.longitude = float(request.POST.get('longitude', event.longitude) or event.longitude)
            event.price = Decimal(request.POST.get('price', str(event.price)) or str(event.price))
            event.total_seats = int(request.POST.get('total_seats', event.total_seats) or event.total_seats)
            img = request.POST.get('image', '').strip()
            if img:
                event.image = img

            date_str = request.POST.get('date', '')
            if date_str:
                from django.utils.dateparse import parse_datetime
                event_date = parse_datetime(date_str)
                if not event_date:
                    from datetime import datetime
                    event_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
                    from django.utils import timezone as tz
                    event_date = tz.make_aware(event_date)
                event.date = event_date

            end_date_str = request.POST.get('end_date', '')
            if end_date_str:
                from django.utils.dateparse import parse_datetime
                end_date = parse_datetime(end_date_str)
                if not end_date:
                    from datetime import datetime
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M')
                    from django.utils import timezone as tz
                    end_date = tz.make_aware(end_date)
                event.end_date = end_date

            if event.is_free:
                event.price = 0
            event.save()
            messages.success(request, f"Event '{event.title}' updated!")
            return redirect('org_dashboard')
        except Exception as e:
            logger.error(f"Error updating event: {e}")
            messages.error(request, f'Error: {e}')

    return render(request, 'events/org_add_event.html', {
        'profile': profile, 'event': event, 'form_data': {}, 'editing': True,
    })
