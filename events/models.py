from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class SiteSettings(models.Model):
    """Admin-configurable site settings — singleton model.
    Update WhatsApp API and Gmail credentials from Django Admin dashboard.
    """
    # ── WhatsApp Business API ──────────────────────────────────────────────
    whatsapp_enabled = models.BooleanField(
        default=False, verbose_name='Enable WhatsApp Notifications'
    )
    whatsapp_api_key = models.CharField(
        max_length=500, blank=True, null=True,
        verbose_name='WhatsApp API Key (Bearer Token)',
        help_text='Meta WhatsApp Business API bearer token from Meta Developer Console'
    )
    whatsapp_phone_number_id = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name='WhatsApp Phone Number ID',
        help_text='Your WhatsApp Business phone number ID from Meta Business Suite'
    )
    whatsapp_business_account_id = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name='WhatsApp Business Account ID'
    )

    # ── Gmail / Email Settings ─────────────────────────────────────────────
    email_enabled = models.BooleanField(
        default=False, verbose_name='Enable Email Notifications'
    )
    gmail_from_name = models.CharField(
        max_length=100, default='Passly Hai', verbose_name='Sender Name'
    )
    gmail_from_email = models.EmailField(
        blank=True, null=True, verbose_name='From Email Address',
        help_text='Email address that appears in the "From" field'
    )
    gmail_host = models.CharField(
        max_length=200, default='smtp.gmail.com', verbose_name='SMTP Host'
    )
    gmail_port = models.IntegerField(default=587, verbose_name='SMTP Port')
    gmail_username = models.EmailField(
        blank=True, null=True, verbose_name='Gmail Username / Email'
    )
    gmail_password = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name='Gmail App Password',
        help_text='Use an App Password — NOT your regular Gmail password. '
                  'Generate at: Google Account → Security → 2-Step Verification → App passwords'
    )
    gmail_use_tls = models.BooleanField(default=True, verbose_name='Use TLS')

    # ── Razorpay Payment Gateway ───────────────────────────────────────────
    razorpay_enabled = models.BooleanField(
        default=True, verbose_name='Enable Razorpay Payments'
    )
    razorpay_key_id = models.CharField(
        max_length=200, blank=True, null=True, verbose_name='Razorpay Key ID'
    )
    razorpay_key_secret = models.CharField(
        max_length=200, blank=True, null=True, verbose_name='Razorpay Key Secret'
    )

    # ── Site Information ───────────────────────────────────────────────────
    site_name = models.CharField(max_length=100, default='Passly Hai', verbose_name='Site Name')
    site_url = models.URLField(default='http://127.0.0.1:8000', verbose_name='Site URL')
    support_email = models.EmailField(blank=True, null=True, verbose_name='Support Email')
    support_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Support Phone')

    # ── Pricing & Fees ─────────────────────────────────────────────────────
    reminder_normal_cost = models.DecimalField(
        max_digits=8, decimal_places=2, default=5.00,
        verbose_name='Normal Reminder Cost (₹)',
        help_text='Cost per attendee for normal email reminder'
    )
    reminder_advance_cost = models.DecimalField(
        max_digits=8, decimal_places=2, default=20.00,
        verbose_name='Advance Reminder Cost (₹)',
        help_text='Cost per attendee for advance WhatsApp reminder'
    )
    payout_charge_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        verbose_name='Payout Processing Charge (%)',
        help_text='Percentage deducted from each payout as processing fee'
    )
    platform_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        verbose_name='Platform Fee (%)',
        help_text='Platform fee percentage charged on each ticket sale'
    )
    min_ticket_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        verbose_name='Minimum Ticket Price (₹)',
        help_text='Minimum price organisers can set for paid tickets'
    )

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return 'Site Settings'

    def save(self, *args, **kwargs):
        self.pk = 1  # Enforce singleton
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # Prevent accidental deletion

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class OrganizerProfile(models.Model):
    """Organizer KYC & bank details for payouts."""
    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='organizer_profile'
    )
    organization_name = models.CharField(max_length=200, blank=True)
    mobile_number = models.CharField(max_length=15)
    email = models.EmailField(blank=True, verbose_name='Contact Email')
    description = models.TextField(blank=True, verbose_name='About / Description')
    website = models.URLField(blank=True, verbose_name='Website URL')
    profile_image = models.URLField(blank=True, verbose_name='Profile Image URL')
    is_public = models.BooleanField(default=True, verbose_name='Show in Public Directory')

    # Bank details
    bank_account_number = models.CharField(max_length=20, blank=True)
    bank_account_number_confirm = models.CharField(
        max_length=20, blank=True, verbose_name='Confirm Account Number',
        help_text='Re-enter account number to confirm'
    )
    bank_ifsc_code = models.CharField(max_length=11, blank=True, verbose_name='IFSC Code')
    bank_account_holder_name = models.CharField(
        max_length=100, blank=True, verbose_name='Beneficiary Name'
    )
    bank_name = models.CharField(max_length=100, blank=True)
    gst_number = models.CharField(
        max_length=15, blank=True, verbose_name='GST Number',
        help_text='15-digit GST Identification Number (optional)'
    )

    # KYC
    pan_card_number = models.CharField(max_length=10, blank=True, verbose_name='PAN Card Number')
    aadhaar_number = models.CharField(max_length=12, blank=True, verbose_name='Aadhaar Number')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    # Wallet
    wallet_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} — {self.organization_name or 'Organizer'}"

    class Meta:
        verbose_name = 'Organizer Profile'
        verbose_name_plural = 'Organizer Profiles'


class TeamMember(models.Model):
    """Team members invited by an organizer (verifiers, managers, etc.)."""
    ROLE_CHOICES = [
        ('verifier', 'Ticket Verifier / QR Scanner'),
        ('manager', 'Event Manager'),
        ('support', 'Support Staff'),
    ]

    organizer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='team_members'
    )
    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='team_member_profile',
        verbose_name='Linked Login Account',
        help_text='Django user account for this team member to log in'
    )
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='verifier')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.get_role_display()}) — {self.organizer.username}"

    class Meta:
        verbose_name = 'Team Member'
        verbose_name_plural = 'Team Members'


class Event(models.Model):
    CATEGORY_CHOICES = [
        ('music', 'Music & Concerts'),
        ('sports', 'Sports'),
        ('tech', 'Technology'),
        ('food', 'Food & Drink'),
        ('art', 'Arts & Culture'),
        ('business', 'Business'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    EVENT_TYPE_CHOICES = [
        ('one_time', 'One Time'),
        ('regular', 'Regular / Recurring'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default='one_time')
    is_free = models.BooleanField(default=False, verbose_name='Free Event')
    is_approved = models.BooleanField(default=True, verbose_name='Admin Approved')

    date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    venue = models.CharField(max_length=200)
    address = models.TextField()
    latitude = models.FloatField(help_text='Latitude for map location', default=20.5937)
    longitude = models.FloatField(help_text='Longitude for map location', default=78.9629)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_seats = models.IntegerField()
    available_seats = models.IntegerField()
    image = models.URLField(
        default='https://via.placeholder.com/800x400/7C3AED/ffffff?text=Event+Image'
    )
    organizer = models.CharField(max_length=100)
    organizer_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='organized_events'
    )

    # Tracking codes (set per-event from admin)
    meta_pixel_id = models.CharField(max_length=50, blank=True, verbose_name='Meta Pixel ID')
    google_analytics_id = models.CharField(
        max_length=50, blank=True, verbose_name='Google Analytics / GTM ID'
    )
    custom_header_code = models.TextField(
        blank=True, verbose_name='Custom Header Code',
        help_text='Raw HTML/JS added inside <head>'
    )
    custom_footer_code = models.TextField(
        blank=True, verbose_name='Custom Footer Code',
        help_text='Raw HTML/JS added before </body>'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return self.title

    @property
    def is_available(self):
        return (
            self.available_seats > 0
            and self.date > timezone.now()
            and self.status == 'published'
            and self.is_approved
        )

    @property
    def is_sold_out(self):
        return self.available_seats <= 0


class TicketType(models.Model):
    """Premium / Normal / VIP ticket tiers per event."""
    TIER_CHOICES = [
        ('normal', 'Normal'),
        ('premium', 'Premium'),
        ('vip', 'VIP'),
    ]

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name='ticket_types'
    )
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='normal')
    name = models.CharField(max_length=100, help_text='e.g., General Admission, VIP Pass')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    total_seats = models.IntegerField()
    available_seats = models.IntegerField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.event.title} — {self.name} (₹{self.price})"

    class Meta:
        verbose_name = 'Ticket Type'
        verbose_name_plural = 'Ticket Types'


class CouponCode(models.Model):
    """Discount coupon codes."""
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage (%)'),
        ('flat', 'Flat Amount (₹)'),
    ]

    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(
        max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='percentage'
    )
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_uses = models.IntegerField(default=100)
    used_count = models.IntegerField(default=0, editable=False)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, null=True, blank=True,
        related_name='coupons',
        help_text='Leave blank to apply to all events'
    )
    minimum_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Minimum booking amount required to use this coupon'
    )

    def __str__(self):
        suffix = '%' if self.discount_type == 'percentage' else '₹'
        return f"{self.code} — {self.discount_value}{suffix} off"

    def is_valid(self):
        now = timezone.now()
        return (
            self.is_active
            and self.used_count < self.max_uses
            and self.valid_from <= now <= self.valid_until
        )

    class Meta:
        verbose_name = 'Coupon Code'
        verbose_name_plural = 'Coupon Codes'


class PayoutRequest(models.Model):
    """Simple payout request from organizer to admin."""
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('paid',     'Paid'),
        ('rejected', 'Rejected'),
    ]

    organizer_profile = models.ForeignKey(
        'OrganizerProfile', on_delete=models.CASCADE, related_name='payout_requests'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    note = models.TextField(blank=True, help_text='Reason or bank note from organizer')
    admin_note = models.TextField(blank=True, help_text='Admin response note')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.organizer_profile.user.username} — ₹{self.amount} ({self.status})"

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payout Request'
        verbose_name_plural = 'Payout Requests'


class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='bookings')
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='bookings', null=True, blank=True
    )
    ticket_type = models.ForeignKey(
        TicketType, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings'
    )
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    number_of_tickets = models.IntegerField(default=1)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon_code = models.ForeignKey(
        CouponCode, on_delete=models.SET_NULL, null=True, blank=True
    )
    booking_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)

    # Notification tracking
    email_sent = models.BooleanField(default=False)
    whatsapp_sent = models.BooleanField(default=False)

    # Razorpay fields
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)

    # Refund
    refund_reason = models.TextField(blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    # Manual booking (imported via CSV)
    is_manual = models.BooleanField(default=False, verbose_name='Manual / Imported Booking')

    # QR scan tracking
    scan_count = models.PositiveIntegerField(default=0, help_text='Number of times this ticket has been scanned at entry')

    class Meta:
        ordering = ['-booking_date']

    def __str__(self):
        return f"{self.name} — {self.event.title}"


class EventDataExport(models.Model):
    """Tracks post-event data exports for 90-day archival and deletion."""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='data_exports')
    exported_at = models.DateTimeField(auto_now_add=True)
    scheduled_delete_at = models.DateTimeField()
    email_sent = models.BooleanField(default=False)
    whatsapp_sent = models.BooleanField(default=False)
    sent_to_email = models.EmailField(blank=True, help_text='Email address the export was sent to')
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-exported_at']
        verbose_name = 'Event Data Export'
        verbose_name_plural = 'Event Data Exports'

    def __str__(self):
        return f"Export: {self.event.title} ({self.exported_at.strftime('%Y-%m-%d')})"
