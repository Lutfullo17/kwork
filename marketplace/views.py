from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Q
from .models import Order, Tag
from .forms import OrderCreateForm
from django.views.generic.edit import UpdateView, DeleteView
from django.urls import reverse_lazy


class OrderListView(View):
    """
    TZ C-bandi: Daraja baland frilanserlarning e'lonlari yuqorida.
    Qidiruv va tag bo'yicha filter qo'llab-quvvatlanadi.
    """
    def get(self, request):
        orders = Order.objects.filter(
            status__in=[Order.Status.OPEN, Order.Status.IN_NEGOTIATION]
        ).select_related('client').prefetch_related('tags', 'chat_rooms__offers')

        # Qidiruv
        query = request.GET.get('q', '').strip()
        if query:
            orders = orders.filter(
                Q(title__icontains=query) | Q(description__icontains=query)
            )

        # Tag bo'yicha filter
        tag_id = request.GET.get('tag')
        if tag_id:
            orders = orders.filter(tags__id=tag_id)

        # Byudjet bo'yicha filter
        min_budget = request.GET.get('min_budget')
        max_budget = request.GET.get('max_budget')
        if min_budget:
            orders = orders.filter(initial_budget__gte=min_budget)
        if max_budget:
            orders = orders.filter(initial_budget__lte=max_budget)

        # Har bir order uchun takliflar sonini hisoblash
        for order in orders:
            order.total_offers = sum(
                room.offers.count() for room in order.chat_rooms.all()
            )

        tags = Tag.objects.all()
        context = {
            'orders': orders,
            'tags': tags,
            'query': query,
            'selected_tag': tag_id,
        }
        return render(request, 'marketplace/order_list.html', context)

class OrderCreateView(LoginRequiredMixin, View):
    login_url = 'accounts:login'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role != 'CLIENT':
            messages.error(request, "Faqat mijozlar buyurtma yarata oladi.")
            return redirect('marketplace:order_list')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = OrderCreateForm()
        return render(request, 'marketplace/order_create.html', {'form': form})

    def post(self, request):
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.client = request.user
            order.status = Order.Status.OPEN
            order.save()
            form.save_m2m()  # teglarni saqlash
            messages.success(request, "Buyurtma muvaffaqiyatli joylashtirildi!")
            return redirect('marketplace:order_detail', pk=order.pk)
        return render(request, 'marketplace/order_create.html', {'form': form})


class OrderDetailView(View):

    def get(self, request, pk):
        order = get_object_or_404(Order, pk=pk)

        already_applied = False
        user_room_id = None

        if request.user.is_authenticated and request.user.role == 'FREELANCER':
            user_room = order.chat_rooms.filter(freelancer=request.user).first()
            if user_room:
                already_applied = True
                user_room_id = user_room.id

        can_apply = (
            request.user.is_authenticated
            and request.user.role == 'FREELANCER'
            and order.status in [Order.Status.OPEN, Order.Status.IN_NEGOTIATION]
            and not already_applied
        )

        context = {
            'order':           order,
            'is_owner':        order.client == request.user,
            'is_freelancer':   request.user.is_authenticated and request.user.role == 'FREELANCER',
            'time_remaining':  order.time_remaining_seconds,
            'already_applied': already_applied,
            'can_apply':       can_apply,
            'user_room_id':    user_room_id,  # ✅ bu yetishmayotgan edi
        }
        return render(request, 'marketplace/order_detail.html', context)


class OrderCancelView(LoginRequiredMixin, View):
    """Faqat buyurtma egasi va faqat OPEN holatda bekor qila oladi."""
    login_url = 'accounts:login'

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk, client=request.user)
        if order.status == Order.Status.OPEN:
            order.status = Order.Status.CANCELLED
            order.save()
            messages.success(request, "Buyurtma bekor qilindi.")
        else:
            messages.error(request, "Bu holatdagi buyurtmani bekor qilib bo'lmaydi.")
        return redirect('marketplace:order_list')


class MyOrdersView(LoginRequiredMixin, View):
    def get(self, request):
        orders = Order.objects.filter(
            client=request.user
        ).prefetch_related(
            'chat_rooms__offers__sender'  # takliflarni oldindan yuklash
        ).order_by('-created_at')
        return render(request, 'marketplace/my_orders.html', {'orders': orders})



class OrderCompleteView(LoginRequiredMixin, View):
    """
    Frilanser ishni topshiradi → mijoz COMPLETED deb tasdiqlaydi.
    Faqat IN_PROGRESS holatida ishlaydi.
    """
    login_url = 'accounts:login'

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)

        # Faqat mijoz tugatishi mumkin
        if request.user != order.client:
            raise PermissionDenied('Faqat buyurtma egasi tugatishi mumkin.')

        if order.status != Order.Status.IN_PROGRESS:
            messages.error(request, 'Faqat jarayondagi buyurtmani tugatish mumkin.')
            return redirect('marketplace:order_detail', pk=pk)

        order.status = Order.Status.COMPLETED
        order.save(update_fields=['status'])

        # Frilanserga bildirishnoma
        from notifications.services import notify_order_completed
        chat_room = order.chat_rooms.first()
        if chat_room and chat_room.freelancer:
            notify_order_completed(
                freelancer=chat_room.freelancer,
                order_title=order.title,
                order_pk=order.pk,
            )

        messages.success(request, 'Buyurtma muvaffaqiyatli yakunlandi!')
        return redirect('marketplace:order_detail', pk=pk)

class OrderEditView(LoginRequiredMixin, UpdateView):
    model = Order
    form_class = OrderCreateForm
    template_name = 'marketplace/order_edit.html'
    login_url = 'accounts:login'

    def get_object(self, queryset=None):
        order = super().get_object(queryset)
        if order.client != self.request.user or order.status != Order.Status.OPEN:
            raise PermissionDenied('Faqat sizning ochiq loyihalaringizni tahrirlashingiz mumkin.')
        return order

    def form_valid(self, form):
        messages.success(self.request, "Buyurtma muvaffaqiyatli tahrirlandi!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('marketplace:my_orders')

class OrderDeleteView(LoginRequiredMixin, DeleteView):
    model = Order
    login_url = 'accounts:login'

    def get_object(self, queryset=None):
        order = super().get_object(queryset)
        if order.client != self.request.user or order.status != Order.Status.OPEN:
            raise PermissionDenied('Faqat sizning ochiq loyihalaringizni o‘chirishingiz mumkin.')
        return order

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Buyurtma o‘chirildi!")
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('marketplace:my_orders')

