import qrcode
from io import BytesIO
from django.core.files import File
from django.conf import settings
from icalendar import Calendar, Event as ICalEvent
from datetime import datetime

def generate_qr_code(booking):
    """Generate QR code for booking"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    
    # QR code data
    qr_data = f"""
    Booking ID: {booking.id}
    Event: {booking.event.title}
    Name: {booking.name}
    Tickets: {booking.number_of_tickets}
    Date: {booking.event.date.strftime('%Y-%m-%d %H:%M')}
    Venue: {booking.event.venue}
    """
    
    qr.add_data(qr_data.strip())
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#667eea", back_color="white")
    
    # Save to BytesIO
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    # Create file
    file_name = f'booking_{booking.id}.png'
    booking.qr_code.save(file_name, File(buffer), save=False)
    booking.save()

def generate_ical(booking):
    """Generate iCal file for calendar sync"""
    cal = Calendar()
    cal.add('prodid', '-//Event Booking App//EN')
    cal.add('version', '2.0')
    
    event = ICalEvent()
    event.add('summary', booking.event.title)
    event.add('dtstart', booking.event.date)
    event.add('dtend', booking.event.end_date or booking.event.date)
    event.add('location', f"{booking.event.venue}, {booking.event.address}")
    event.add('description', f"{booking.event.description}\n\nBooking ID: {booking.id}\nTickets: {booking.number_of_tickets}")
    event.add('uid', f'{booking.id}@eventbooking.com')
    
    cal.add_component(event)
    
    return cal.to_ical()
