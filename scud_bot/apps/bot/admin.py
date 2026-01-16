from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from django.urls import path
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from .models import Transaction, Employee, Terminal


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['emp_code', 'name', 'telegram_username',
                    'send_notifications', 'transaction_count_link',
                    'last_seen', 'status', 'unlinked_count']
    list_filter = ['send_notifications']
    search_fields = ['name', 'emp_code', 'telegram_username']
    actions = ['enable_notifications', 'disable_notifications', 'link_transactions']

    def transaction_count_link(self, obj):
        count = Transaction.objects.filter(employee=obj).count()
        url = f'/admin/bot/transaction/?employee__id__exact={obj.id}'
        return format_html('<a href="{}">{} записей</a>', url, count)

    transaction_count_link.short_description = 'Записи'

    def last_seen(self, obj):
        last_transaction = Transaction.objects.filter(
            employee=obj
        ).order_by('-punch_time').first()

        if last_transaction:
            return last_transaction.punch_time.strftime('%d.%m.%Y %H:%M')
        return 'Никогда'

    last_seen.short_description = 'Последний проход'

    def status(self, obj):
        if not obj.can_receive_notifications:
            return 'Не настроен'

        # Проверяем активность за последние 7 дней
        week_ago = timezone.now() - timedelta(days=7)
        recent = Transaction.objects.filter(
            employee=obj,
            punch_time__gte=week_ago
        ).exists()

        if recent:
            return 'Активен'
        return 'Неактивен'

    status.short_description = 'Статус'

    def unlinked_count(self, obj):
        """Количество непривязанных записей этого сотрудника"""
        # Используем lazy import
        Transaction = obj._meta.apps.get_model('bot', 'Transaction')

        count = Transaction.objects.filter(
            emp_code=obj.emp_code,
            employee__isnull=True
        ).count()

        if count > 0:
            url = f'/admin/bot/transaction/?emp_code={obj.emp_code}&employee__isnull=1'
            return format_html(
                '<a href="{}" style="color: orange;">⚠ {} непривязанных</a>',
                url, count
            )
        return '✓ Все привязаны'

    unlinked_count.short_description = 'Непривязанные'

    def enable_notifications(self, request, queryset):
        updated = queryset.update(send_notifications=True)
        self.message_user(request, f"Уведомления включены для {updated} сотрудников")

    enable_notifications.short_description = "Включить уведомления"

    def disable_notifications(self, request, queryset):
        updated = queryset.update(send_notifications=False)
        self.message_user(request, f"Уведомления выключены для {updated} сотрудников")

    disable_notifications.short_description = "Выключить уведомления"

    def link_transactions(self, request, queryset):
        for employee in queryset:
            linked = employee.link_existing_transactions()
            self.message_user(
                request,
                f"Для {employee.name} привязано {linked} записей"
            )

    link_transactions.short_description = "Привязать записи проходов"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['employee_link', 'terminal', 'punch_time',
                    'punch_state_display', 'verify_type_display']
    list_filter = ['punch_state', 'terminal', 'employee', 'punch_time']
    search_fields = ['emp_code', 'employee__name']
    date_hierarchy = 'punch_time'
    readonly_fields = ['skud_id', 'emp_code', 'created_at']

    fieldsets = [
        ('Основная информация', {
            'fields': ['skud_id', 'employee', 'emp_code', 'terminal']
        }),
        ('Детали прохода', {
            'fields': ['punch_time', 'punch_state', 'verify_type']
        }),
        ('Системное', {
            'fields': ['created_at']
        }),
    ]

    def employee_link(self, obj):
        if obj.employee:
            url = f'/admin/bot/transaction/?employee__id__exact={obj.employee.id}'
            return format_html('<a href="{}">{}</a>', url, str(obj.employee))
        else:
            # Ссылка на поиск по коду
            url = f'/admin/bot/transaction/?q={obj.emp_code}'
            return format_html('<a href="{}">Сотр. {}</a>', url, obj.emp_code)

    employee_link.short_description = "Сотрудник"

    def punch_state_display(self, obj):
        if obj.punch_state in ['0', 'I']:
            return format_html('<span style="color: green;">▶ Вход</span>')
        return format_html('<span style="color: red;">◀ Выход</span>')

    punch_state_display.short_description = "Тип"

    def verify_type_display(self, obj):
        types = {
            1: 'Отпечаток',
            4: 'Карта',
            15: 'Лицо'
        }
        return types.get(obj.verify_type, f'{obj.verify_type}')

    verify_type_display.short_description = "Способ"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by('-punch_time')


@admin.register(Terminal)
class TerminalAdmin(admin.ModelAdmin):
    list_display = ['terminal_alias', 'terminal_sn', 'area_alias',
                    'is_monitored', 'transaction_count', 'last_activity']
    list_filter = ['is_monitored', 'area_alias']
    search_fields = ['terminal_alias', 'terminal_sn', 'area_alias']
    actions = ['enable_monitoring', 'disable_monitoring']

    def transaction_count(self, obj):
        count = Transaction.objects.filter(terminal=obj).count()
        url = f'/admin/bot/transaction/?terminal__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)

    transaction_count.short_description = 'Записей'

    def last_activity(self, obj):
        last = Transaction.objects.filter(
            terminal=obj
        ).order_by('-punch_time').first()
        if last:
            return last.punch_time.strftime('%d.%m.%Y %H:%M')
        return 'Нет данных'

    last_activity.short_description = 'Последняя активность'

    def enable_monitoring(self, request, queryset):
        updated = queryset.update(is_monitored=True)
        self.message_user(request, f"Мониторинг включен для {updated} терминалов")

    enable_monitoring.short_description = "Включить мониторинг"

    def disable_monitoring(self, request, queryset):
        updated = queryset.update(is_monitored=False)
        self.message_user(request, f"Мониторинг выключен для {updated} терминалов")

    disable_monitoring.short_description = "Выключить мониторинг"


# Статистика в админке
@staff_member_required
def admin_stats(request):
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    employees = Employee.objects.annotate(
        transaction_count=Count('transaction')
    ).order_by('-transaction_count')[:10]

    daily_stats = Transaction.objects.filter(
        punch_time__date__gte=week_ago
    ).extra(
        {'date': "date(punch_time)"}
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')

    top_terminals = Terminal.objects.annotate(
        transaction_count=Count('transaction')
    ).filter(transaction_count__gt=0).order_by('-transaction_count')[:10]

    unlinked_count = Transaction.objects.filter(employee__isnull=True).count()

    context = {
        'employees': employees,
        'daily_stats': daily_stats,
        'top_terminals': top_terminals,
        'unlinked_count': unlinked_count,
        'total_transactions': Transaction.objects.count(),
        'total_employees': Employee.objects.count(),
        'total_terminals': Terminal.objects.count(),
    }

    return render(request, 'admin/stats.html', context)


# Добавляем ссылку в админку
def get_admin_urls(urls):
    def get_urls():
        my_urls = [
            path('stats/', admin.site.admin_view(admin_stats), name='admin_stats'),
        ]
        return my_urls + urls

    return get_urls


admin.site.get_urls = get_admin_urls(admin.site.get_urls())