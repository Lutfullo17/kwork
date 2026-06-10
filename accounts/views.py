from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages

from .models import User, Profile, Emailcode
from .utilis import send_email_code


class RegisterView(View):

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('marketplace:order_list')
        return render(request, 'accounts/register.html')

    def post(self, request):
        full_name = request.POST.get('full_name', '').strip()
        email     = request.POST.get('email', '').strip().lower()
        password  = request.POST.get('password', '')
        role      = request.POST.get('role', '')

        if not all([full_name, email, password, role]):
            return render(request, 'accounts/register.html', {
                'error': 'Barcha maydonlarni to\'ldiring',
                'full_name': full_name,
                'email': email,
                'role': role,
            })

        if role not in ('CLIENT', 'FREELANCER'):
            return render(request, 'accounts/register.html', {
                'error': 'Noto\'g\'ri rol tanlandi',
            })

        if len(password) < 8:
            return render(request, 'accounts/register.html', {
                'error': 'Parol kamida 8 ta belgidan iborat bo\'lishi kerak',
                'full_name': full_name,
                'email': email,
                'role': role,
            })

        user_exists = User.objects.filter(email=email).exists()

        if not user_exists:
            user = User.objects.create_user(
                username  = email,
                email     = email,
                password  = password,
                full_name = full_name,
                role      = role,
                is_active = False,
            )
            send_email_code(user)

        request.session['pending_email'] = email
        return redirect('accounts:verify_email')


class VerifyEmailView(View):

    def get(self, request):
        email = request.session.get('pending_email')
        if not email:
            return redirect('accounts:register')
        return render(request, 'accounts/verify_email.html', {'email': email})

    @method_decorator(ratelimit(key='ip', rate='5/10m', method='POST', block=True))
    def post(self, request):
        email = request.session.get('pending_email')
        if not email:
            return redirect('accounts:register')

        code = request.POST.get('code', '').strip()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return redirect('accounts:register')

        email_code = Emailcode.objects.filter(
            user         = user,
            code         = code,
            is_activated = False,
        ).last()

        if not email_code:
            return render(request, 'accounts/verify_email.html', {
                'email': email,
                'error': 'Kod noto\'g\'ri',
            })

        if email_code.is_expired():
            email_code.delete()
            return render(request, 'accounts/verify_email.html', {
                'email': email,
                'error': 'Kod muddati o\'tgan. Qayta yuboring.',
            })

        email_code.is_activated = True
        email_code.save(update_fields=['is_activated'])

        user.is_active = True
        user.save(update_fields=['is_active'])

        # Sessiyani tozalash
        del request.session['pending_email']

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('marketplace:order_list')


class ResendCodeView(View):

    @method_decorator(ratelimit(key='ip', rate='3/10m', method='GET', block=True))
    def get(self, request):
        email = request.session.get('pending_email')
        if not email:
            return redirect('accounts:register')

        try:
            user = User.objects.get(email=email, is_active=False)
        except User.DoesNotExist:
            return redirect('accounts:register')

        # Eski muddati o'tgan kodlarni tozalash
        Emailcode.objects.filter(user=user, is_activated=False).delete()

        send_email_code(user)
        return redirect('accounts:verify_email')



class LoginView(View):
    """Foydalanuvchi tizimga kirishi."""

    def get(self, request):
        # Agar foydalanuvchi allaqachon kirgan bo'lsa, asosiy sahifaga yuboramiz
        if request.user.is_authenticated:
            return redirect('marketplace:order_list')
        return render(request, 'accounts/login.html')

    @method_decorator(ratelimit(key='ip', rate='5/5m', method='POST', block=True))
    def post(self, request):
        email    = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        if not email or not password:
            return render(request, 'accounts/login.html', {
                'error': 'Email va parolni kiriting',
                'email': email
            })


        user = authenticate(request, username=email, password=password)

        if user is not None:
            if user.is_active:
                login(request, user)
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('marketplace:order_list')
            else:
                request.session['pending_email'] = email
                return render(request, 'accounts/login.html', {
                    'error': 'Hisobingiz faol emas. Iltimos, emailni tasdiqlang.',
                    'email': email,
                    'is_not_active': True
                })
        else:
            return render(request, 'accounts/login.html', {
                'error': 'Email yoki parol noto\'g\'ri',
                'email': email
            })

def logout_out(request):
    logout(request)
    return redirect('marketplace:order_list')


class ProfileView(View):

    def get(self, request, pk=None):
        if pk:
            profile_user = get_object_or_404(User, pk=pk)
        elif request.user.is_authenticated:
            profile_user = request.user
        else:
            return redirect('accounts:login')

        profile, _ = Profile.objects.get_or_create(user=profile_user)
        from reviews.models import Review
        from django.db.models import Avg

        reviews = (
            Review.objects
            .filter(freelancer=profile_user)
            .select_related('reviewer', 'order')
            .order_by('-created_at')
        )
        avg_stars = reviews.aggregate(avg=Avg('stars'))['avg'] or 0

        level_labels = {1: 'Boshlovchi', 2: "O'rta", 3: 'Ekspert'}
        level_colors = {1: '#8a8278',    2: '#c8a96e', 3: '#3d7a5e'}

        return render(request, 'accounts/profile.html', {
            'profile_user':   profile_user,
            'profile':        profile,
            'reviews':        reviews,
            'avg_stars':      round(float(avg_stars), 1),
            'reviews_count':  reviews.count(),
            'is_own_profile': request.user == profile_user,
            'level_label':    level_labels.get(profile.level, 'Boshlovchi'),
            'level_color':    level_colors.get(profile.level, '#8a8278'),
        })

class ProfileEditView(LoginRequiredMixin, View):
    login_url = 'accounts:login'

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        skills_str = ', '.join(profile.skills) if profile.skills else ''
        return render(request, 'accounts/profile_edit.html', {
            'profile': profile,
            'skills_str': skills_str,
        })

    def post(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        user = request.user
        full_name = request.POST.get('full_name', '').strip()
        if full_name:
            user.full_name = full_name
            user.save(update_fields=['full_name'])

        if 'avatar' in request.FILES:
            user.avatar = request.FILES['avatar']
            user.save(update_fields=['avatar'])

        profile.bio = request.POST.get('bio', '').strip() or None

        skills_raw = request.POST.get('skills', '')
        profile.skills = [
            s.strip() for s in skills_raw.split(',') if s.strip()
        ]

        profile.save(update_fields=['bio', 'skills'])

        messages.success(request, 'Profil muvaffaqiyatli yangilandi!')
        return redirect('accounts:profile')