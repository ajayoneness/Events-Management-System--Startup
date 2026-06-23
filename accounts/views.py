from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from .forms import SignUpForm, EmailLoginForm, LoginForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from events.models import Event, Booking, OrganizerProfile
import logging
import re

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


def register_organizer_view(request):
    """Registration for event organisers — creates User + OrganizerProfile (pending verification)."""
    if request.user.is_authenticated:
        # Already logged in? Check if they already have an org profile
        if hasattr(request.user, 'organizer_profile'):
            return redirect('org_dashboard')
        # Allow logged-in user to create an org profile
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        org_name = request.POST.get('organization_name', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        description = request.POST.get('description', '').strip()

        errors = []
        if not first_name:
            errors.append('First name is required.')
        if not email:
            errors.append('Email is required.')
        if not phone:
            errors.append('Phone number is required.')
        if not org_name:
            errors.append('Organisation name is required.')

        if request.user.is_authenticated:
            # Existing user creating org profile
            user = request.user
            if hasattr(user, 'organizer_profile'):
                messages.info(request, 'You already have an organiser profile.')
                return redirect('org_dashboard')
        else:
            # New user registration
            if not password1 or len(password1) < 8:
                errors.append('Password must be at least 8 characters.')
            if password1 != password2:
                errors.append('Passwords do not match.')
            if User.objects.filter(email__iexact=email).exists():
                errors.append('An account with this email already exists. Please login instead.')
            user = None

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'accounts/register_organizer.html', {
                'form_data': request.POST,
            })

        # Create user if new
        if not request.user.is_authenticated:
            base_username = re.sub(r'[^a-z0-9]', '', org_name.lower())[:20] or re.sub(r'[^a-z0-9]', '', email.split('@')[0])[:20] or 'org'
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            user = User.objects.create_user(
                username=username, email=email, password=password1,
                first_name=first_name, last_name=last_name,
            )
            login(request, user)
        else:
            user.first_name = first_name or user.first_name
            user.last_name = last_name or user.last_name
            user.save()

        # Create OrganizerProfile
        OrganizerProfile.objects.create(
            user=user,
            organization_name=org_name,
            mobile_number=phone,
            email=email,
            description=description,
            status='pending',
        )
        messages.success(request, f"Organisation '{org_name}' registered! Your account is pending admin verification.")
        return redirect('org_dashboard')

    return render(request, 'accounts/register_organizer.html', {'form_data': {}})


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

        # Username-based authentication (admin, staff, team members, organisers)
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
            # Redirect organisers to org dashboard
            if hasattr(user, 'organizer_profile'):
                messages.success(request, f"Welcome back, {user.organizer_profile.organization_name or user.username}!")
                next_url = request.GET.get('next')
                return redirect(next_url if next_url else 'org_dashboard')
            # Redirect staff to admin dashboard
            if user.is_staff:
                messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
                next_url = request.GET.get('next')
                return redirect(next_url if next_url else 'sales_dashboard')
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
