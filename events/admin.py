from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.http import HttpResponse
import csv

from .models import (
    SiteSettings, Event, Booking, TicketType,
    CouponCode, OrganizerProfile, TeamMember, PayoutRequest, EventDataExport,
)

admin.site.site_header = "Passly Hai Admin"
admin.site.site_title = "Passly Hai Admin Portal"
admin.site.index_title = "Welcome to Passly Hai Administration"


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('📱 WhatsApp Business API', {
            'fields': ('whatsapp_enabled', 'whatsapp_api_key', 'whatsapp_phone_number_id', 'whatsapp_business_account_id'),
        }),
        ('✉️ Gmail / Email Settings', {
            'fields': ('email_enabled', 'gmail_from_name', 'gmail_from_email', 'gmail_host', 'gmail_port', 'gmail_username', 'gmail_password', 'gmail_use_tls'),
        }),
        ('💳 Razorpay Payment Gateway', {
            'fields': ('razorpay_enabled', 'razorpay_key_id', 'razorpay_key_secret'),
        }),
        ('🌐 Site Information', {
            'fields': ('site_name', 'site_url', 'support_email', 'support_phone'),
        }),
        ('💰 Pricing & Fees', {
            'fields': ('reminder_normal_cost', 'reminder_advance_cost', 'payout_charge_percent', 'platform_fee_percent', 'min_ticket_price'),
            'description': (
                '<strong>Reminder costs</strong> are charged per attendee when sending reminders. '
                '<strong>Payout charge</strong> is deducted from each payout. '
                '<strong>Min ticket price</strong> prevents organisers from setting prices too low.'
            ),
        }),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj, _ = SiteSettings.objects.get_or_create(pk=1)
        from django.shortcuts import redirect
        return redirect(f'/admin/events/sitesettings/{obj.pk}/change/')


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1
    fields = ['tier', 'name', 'price', 'total_seats', 'available_seats', 'description', 'is_active']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'colored_status', 'date', 'venue', 'price', 'available_seats', 'is_free', 'is_approved']
    list_filter  = ['category', 'status', 'is_free', 'is_approved', 'event_type']
    search_fields = ['title', 'venue', 'organizer']
    readonly_fields = ['id', 'created_at', 'updated_at']
    inlines = [TicketTypeInline]
    actions = ['action_approve', 'action_mark_completed']

    fieldsets = (
        ('Basic Info', {'fields': ('id', 'title', 'description', 'category', 'status', 'event_type', 'is_free', 'is_approved')}),
        ('Scheduling', {'fields': ('date', 'end_date')}),
        ('Location', {'fields': ('venue', 'address', 'latitude', 'longitude')}),
        ('Tickets & Pricing', {'fields': ('price', 'total_seats', 'available_seats', 'image')}),
        ('Organizer', {'fields': ('organizer', 'organizer_user')}),
        ('Tracking Codes', {'fields': ('meta_pixel_id', 'google_analytics_id', 'custom_header_code', 'custom_footer_code'), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def colored_status(self, obj):
        colors = {'draft': '#6b7280', 'published': '#059669', 'completed': '#2563eb', 'cancelled': '#dc2626'}
        color = colors.get(obj.status, '#6b7280')
        return format_html('<span style="background:{};color:#fff;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600;">{}</span>', color, obj.get_status_display())
    colored_status.short_description = 'Status'

    def action_approve(self, request, queryset):
        queryset.update(is_approved=True, status='published')
        self.message_user(request, f'{queryset.count()} event(s) approved and published.')
    action_approve.short_description = '✅ Approve & Publish'

    def action_mark_completed(self, request, queryset):
        queryset.update(status='completed')
        self.message_user(request, f'{queryset.count()} event(s) marked as completed.')
    action_mark_completed.short_description = '✔️ Mark as Completed'


def export_bookings_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="attendees.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Email', 'Phone', 'Event', 'Tickets', 'Amount', 'Status', 'Booking Date', 'Manual'])
    for b in queryset:
        writer.writerow([b.name, b.email, b.phone, b.event.title, b.number_of_tickets, b.total_amount, b.status, b.booking_date.strftime('%Y-%m-%d %H:%M'), 'Yes' if b.is_manual else 'No'])
    return response
export_bookings_csv.short_description = '📥 Export selected bookings to CSV'


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['name', 'event', 'number_of_tickets', 'total_amount', 'booking_date', 'colored_booking_status', 'email_sent', 'whatsapp_sent', 'is_manual']
    list_filter  = ['status', 'booking_date', 'email_sent', 'whatsapp_sent', 'is_manual']
    search_fields = ['name', 'email', 'phone', 'event__title']
    readonly_fields = ['id', 'booking_date', 'qr_code', 'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature']
    actions = [export_bookings_csv, 'action_send_email', 'action_send_whatsapp', 'action_mark_refunded']

    def colored_booking_status(self, obj):
        colors = {'pending': '#d97706', 'confirmed': '#059669', 'cancelled': '#6b7280', 'failed': '#dc2626', 'refunded': '#2563eb'}
        color = colors.get(obj.status, '#6b7280')
        return format_html('<span style="background:{};color:#fff;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600;">{}</span>', color, obj.get_status_display())
    colored_booking_status.short_description = 'Status'

    def action_send_email(self, request, queryset):
        from .notifications import send_booking_email
        count = sum(1 for b in queryset if send_booking_email(b))
        self.message_user(request, f'Confirmation email sent for {count} booking(s).')
    action_send_email.short_description = '✉️ Send confirmation email'

    def action_send_whatsapp(self, request, queryset):
        from .notifications import send_whatsapp_notification
        count = sum(1 for b in queryset if send_whatsapp_notification(b))
        self.message_user(request, f'WhatsApp notification sent for {count} bookings.')
    action_send_whatsapp.short_description = '📱 Send WhatsApp notification'

    def action_mark_refunded(self, request, queryset):
        queryset.update(status='refunded', refunded_at=timezone.now())
        self.message_user(request, f'{queryset.count()} bookings marked as refunded.')
    action_mark_refunded.short_description = '↩️ Mark as refunded'


@admin.register(CouponCode)
class CouponCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'discount_value', 'used_count', 'max_uses', 'valid_until', 'is_active']
    list_filter  = ['discount_type', 'is_active']
    search_fields = ['code']
    readonly_fields = ['used_count']


@admin.register(OrganizerProfile)
class OrganizerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization_name', 'mobile_number', 'colored_org_status', 'wallet_balance', 'created_at']
    list_filter  = ['status', 'is_public']
    search_fields = ['user__username', 'user__email', 'organization_name', 'mobile_number', 'gst_number']
    readonly_fields = ['wallet_balance', 'created_at', 'updated_at']
    actions = ['action_verify', 'action_reject']

    fieldsets = (
        ('User & Organization', {
            'fields': ('user', 'organization_name', 'mobile_number', 'email', 'description', 'website', 'profile_image', 'is_public'),
        }),
        ('Bank Details (for Payout)', {
            'fields': ('bank_account_holder_name', 'bank_account_number', 'bank_account_number_confirm', 'bank_ifsc_code', 'bank_name'),
        }),
        ('Tax & Compliance', {
            'fields': ('pan_card_number', 'aadhaar_number', 'gst_number'),
        }),
        ('Verification Status', {
            'fields': ('status', 'verified_at', 'rejection_reason'),
        }),
        ('Wallet', {
            'fields': ('wallet_balance',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def colored_org_status(self, obj):
        colors = {'pending': '#d97706', 'verified': '#059669', 'rejected': '#dc2626'}
        color = colors.get(obj.status, '#6b7280')
        return format_html('<span style="background:{};color:#fff;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600;">{}</span>', color, obj.get_status_display())
    colored_org_status.short_description = 'Status'

    def action_verify(self, request, queryset):
        queryset.update(status='verified', verified_at=timezone.now())
        self.message_user(request, f'{queryset.count()} organiser(s) verified.')
    action_verify.short_description = '✅ Verify organiser'

    def action_reject(self, request, queryset):
        queryset.update(status='rejected')
        self.message_user(request, f'{queryset.count()} organiser(s) rejected.')
    action_reject.short_description = '❌ Reject organiser'


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display  = ['organizer_profile', 'amount', 'colored_payout_status', 'created_at', 'processed_at']
    list_filter   = ['status']
    search_fields = ['organizer_profile__user__username', 'organizer_profile__organization_name']
    readonly_fields = ['created_at']
    actions = ['action_mark_paid', 'action_mark_rejected']

    def colored_payout_status(self, obj):
        colors = {'pending': '#d97706', 'approved': '#2563eb', 'paid': '#059669', 'rejected': '#dc2626'}
        color = colors.get(obj.status, '#6b7280')
        return format_html('<span style="background:{};color:#fff;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600;">{}</span>', color, obj.get_status_display())
    colored_payout_status.short_description = 'Status'

    def action_mark_paid(self, request, queryset):
        queryset.update(status='paid', processed_at=timezone.now())
        self.message_user(request, f'{queryset.count()} payout(s) marked as paid.')
    action_mark_paid.short_description = '✅ Mark as Paid'

    def action_mark_rejected(self, request, queryset):
        queryset.update(status='rejected', processed_at=timezone.now())
        self.message_user(request, f'{queryset.count()} payout(s) rejected.')
    action_mark_rejected.short_description = '❌ Mark as Rejected'


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display  = ['name', 'email', 'phone', 'role', 'organizer', 'user', 'is_active', 'created_at']
    list_filter   = ['role', 'is_active']
    search_fields = ['name', 'email', 'organizer__username', 'user__username']
    list_editable = ['is_active']
    raw_id_fields = ['user']

    fieldsets = (
        ('Member Info', {'fields': ('organizer', 'name', 'email', 'phone', 'role', 'is_active')}),
        ('Login Account', {
            'fields': ('user',),
            'description': 'Link a Django User account for this team member to log in. '
                           'Create the user first, then link here.',
        }),
    )


@admin.register(EventDataExport)
class EventDataExportAdmin(admin.ModelAdmin):
    list_display = ['event', 'exported_at', 'scheduled_delete_at', 'email_sent', 'is_deleted']
    list_filter  = ['email_sent', 'is_deleted']
    search_fields = ['event__title', 'sent_to_email']
    readonly_fields = ['exported_at']
    actions = ['action_mark_deleted']

    def action_mark_deleted(self, request, queryset):
        queryset.update(is_deleted=True, deleted_at=timezone.now())
        self.message_user(request, f'{queryset.count()} export record(s) marked as deleted.')
    action_mark_deleted.short_description = '🗑️ Mark as Deleted'
