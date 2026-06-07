from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from .forms import SignUpForm, EmailLoginForm, LoginForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from events.models import Event, Booking
import logging

logger = logging.getLogger(__name__)


def register_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created! Welcome to Passly Hai.")
            return redirect('event_list')
        else:
            messages.error(request, "Registration failed. Please check the form.")
    else:
        form = SignUpForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    """Login with email for regular users; username for admin/staff/team members."""
    if request.method == 'POST':
        login_tab      = request.POST.get('login_tab', 'email')
        email          = request.POST.get('email', '').strip().lower()
        username_input = request.POST.get('username', '').strip()
        # Each tab uses its own password field name to avoid collisions
        password = (
            request.POST.get('email_password', '')
            if login_tab == 'email'
            else request.POST.get('username_password', '')
        )

        user = None

        # Email-based authentication (regular users)
        if login_tab == 'email' and email:
            u = User.objects.filter(email__iexact=email).order_by('id').first()
            if u:
                user = authenticate(request, username=u.username, password=password)
            # Fallback: treat input as username (for team members using the email field)
            if user is None:
                user = authenticate(request, username=email, password=password)

        # Username-based authentication (admin, staff, team members)
        if login_tab == 'username' and username_input:
            user = authenticate(request, username=username_input, password=password)

        if user is not None:
            login(request, user)
            # Check if this user is a QR scanner team member
            try:
                member = user.team_member_profile
                if member.role == 'verifier' and member.is_active:
                    messages.success(request, f"Welcome, {user.get_full_name() or user.username}! QR Scanner ready.")
                    return redirect('qr_scanner')
            except Exception:
                pass
            messages.success(request, f"Welcome back, {user.get_full_name() or user.email or user.username}!")
            next_url = request.GET.get('next', 'event_list')
            return redirect(next_url)
        else:
            messages.error(request, "Invalid email/username or password.")

    return render(request, 'accounts/login.html', {})


def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('event_list')


@login_required
def profile_view(request):
    """Display user profile with booking stats."""
    bookings = Booking.objects.filter(user=request.user).order_by('-booking_date')
    confirmed = bookings.filter(status='confirmed')
    total_spent = sum(b.total_amount for b in confirmed)
    context = {
        'bookings': bookings,
        'total_count': bookings.count(),
        'confirmed_count': confirmed.count(),
        'pending_count': bookings.filter(status='pending').count(),
        'total_spent': int(total_spent),
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def profile_update(request):
    """Handle profile edit form submission."""
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name  = request.POST.get('last_name', '').strip()
        new_email = request.POST.get('email', '').strip().lower()
        # Check email uniqueness (allow same email for current user)
        if new_email and new_email != user.email:
            if User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
                messages.error(request, 'That email is already in use by another account.')
                return redirect('accounts:profile')
        user.email = new_email or user.email
        user.save()
        messages.success(request, 'Profile updated successfully!')
    return redirect('accounts:profile')
