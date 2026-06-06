"""
Notification helpers — WhatsApp Business API & Gmail SMTP.
Credentials are loaded dynamically from SiteSettings (Admin Dashboard).
"""
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _get_settings():
    from .models import SiteSettings
    return SiteSettings.get_settings()


# ── WhatsApp ───────────────────────────────────────────────────────────────

def send_whatsapp_notification(booking):
    """Send booking confirmation via Meta WhatsApp Business API."""
    try:
        import requests as req
    except ImportError:
        logger.error("'requests' package not installed. Run: pip install requests")
        return False

    try:
        cfg = _get_settings()

        if not cfg.whatsapp_enabled:
            return False
        if not cfg.whatsapp_api_key or not cfg.whatsapp_phone_number_id:
            logger.warning("WhatsApp API not fully configured in Site Settings")
            return False

        phone = booking.phone.strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if not phone.startswith('+'):
            phone = '91' + phone  # Default country code India
        else:
            phone = phone[1:]  # Remove leading +

        url = f"https://graph.facebook.com/v18.0/{cfg.whatsapp_phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {cfg.whatsapp_api_key}",
            "Content-Type": "application/json",
        }

        body = (
            f"🎉 *Booking Confirmed!*\n\n"
            f"Hello {booking.name},\n\n"
            f"Your booking is confirmed!\n\n"
            f"*Event:* {booking.event.title}\n"
            f"*Date:* {booking.event.date.strftime('%d %b %Y, %I:%M %p')}\n"
            f"*Venue:* {booking.event.venue}\n"
            f"*Tickets:* {booking.number_of_tickets}\n"
            f"*Amount Paid:* ₹{booking.total_amount}\n"
            f"*Booking ID:* {str(booking.id)[:8].upper()}\n\n"
            f"Show your QR code at the entrance.\n\n"
            f"— {cfg.site_name}"
        )

        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": body},
        }

        response = req.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"WhatsApp sent to {booking.phone} for booking {booking.id}")
            return True
        else:
            logger.error(f"WhatsApp API error {response.status_code}: {response.text}")
            return False

    except Exception as exc:
        logger.error(f"WhatsApp notification failed: {exc}")
        return False


# ── Email ──────────────────────────────────────────────────────────────────

def send_booking_email(booking):
    """Send booking confirmation email via Gmail SMTP."""
    try:
        cfg = _get_settings()

        if not cfg.email_enabled:
            return False
        if not cfg.gmail_username or not cfg.gmail_password:
            logger.warning("Gmail credentials not configured in Site Settings")
            return False

        from_name = cfg.gmail_from_name or cfg.site_name
        from_email = cfg.gmail_from_email or cfg.gmail_username

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Booking Confirmed — {booking.event.title}"
        msg['From'] = f"{from_name} <{from_email}>"
        msg['To'] = booking.email

        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F5F3FF;font-family:'Inter',Arial,sans-serif;">
  <div style="max-width:600px;margin:30px auto;background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 8px 30px rgba(124,58,237,.15);">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#7C3AED 0%,#4C1D95 100%);padding:40px 30px;text-align:center;">
      <div style="font-size:48px;">🎉</div>
      <h1 style="color:#fff;margin:10px 0 0;font-size:26px;font-weight:800;letter-spacing:-.5px;">Booking Confirmed!</h1>
      <p style="color:rgba(255,255,255,.8);margin:8px 0 0;font-size:14px;">Your tickets are reserved.</p>
    </div>

    <!-- Body -->
    <div style="padding:32px 30px;">
      <p style="font-size:16px;color:#1e1b4b;margin:0 0 8px;">Hello <strong>{booking.name}</strong>,</p>
      <p style="color:#6b7280;font-size:14px;margin:0 0 24px;">
        Great news! Your booking has been successfully confirmed. Here are your details:
      </p>

      <!-- Details box -->
      <div style="background:#F5F3FF;border-radius:12px;padding:24px;margin:0 0 24px;">
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <tr>
            <td style="padding:7px 0;color:#6b7280;width:38%;vertical-align:top;">Event</td>
            <td style="padding:7px 0;color:#1e1b4b;font-weight:700;">{booking.event.title}</td>
          </tr>
          <tr>
            <td style="padding:7px 0;color:#6b7280;">Date &amp; Time</td>
            <td style="padding:7px 0;color:#1e1b4b;font-weight:600;">{booking.event.date.strftime('%d %b %Y, %I:%M %p')}</td>
          </tr>
          <tr>
            <td style="padding:7px 0;color:#6b7280;">Venue</td>
            <td style="padding:7px 0;color:#1e1b4b;font-weight:600;">{booking.event.venue}</td>
          </tr>
          <tr>
            <td style="padding:7px 0;color:#6b7280;">Tickets</td>
            <td style="padding:7px 0;color:#1e1b4b;font-weight:600;">{booking.number_of_tickets}</td>
          </tr>
          <tr>
            <td style="padding:7px 0;color:#6b7280;">Amount Paid</td>
            <td style="padding:7px 0;color:#7C3AED;font-weight:800;font-size:20px;">₹{booking.total_amount}</td>
          </tr>
          <tr>
            <td style="padding:7px 0;color:#6b7280;">Booking ID</td>
            <td style="padding:7px 0;color:#1e1b4b;font-weight:600;font-size:12px;letter-spacing:1px;">{str(booking.id)[:8].upper()}</td>
          </tr>
        </table>
      </div>

      <p style="color:#6b7280;font-size:13px;margin:0 0 24px;">
        Show your QR code at the venue entrance. Visit your bookings page to download your e-ticket.
      </p>

      <div style="text-align:center;margin:24px 0;">
        <a href="{cfg.site_url}/my-bookings/"
           style="display:inline-block;background:linear-gradient(135deg,#7C3AED,#4C1D95);color:#fff;padding:14px 32px;border-radius:50px;text-decoration:none;font-weight:700;font-size:14px;letter-spacing:.3px;">
          View My Tickets →
        </a>
      </div>
    </div>

    <!-- Footer -->
    <div style="background:#F5F3FF;padding:20px 30px;text-align:center;border-top:1px solid #ede9fe;">
      <p style="color:#9ca3af;font-size:12px;margin:0;">
        © {cfg.site_name}
        {f' | {cfg.support_email}' if cfg.support_email else ''}
        {f' | {cfg.support_phone}' if cfg.support_phone else ''}
      </p>
    </div>
  </div>
</body>
</html>"""

        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP(cfg.gmail_host, cfg.gmail_port, timeout=15) as server:
            if cfg.gmail_use_tls:
                server.starttls()
            server.login(cfg.gmail_username, cfg.gmail_password)
            server.sendmail(from_email, booking.email, msg.as_string())

        logger.info(f"Confirmation email sent to {booking.email} for booking {booking.id}")
        return True

    except Exception as exc:
        logger.error(f"Email sending failed: {exc}")
        return False
