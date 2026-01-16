from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.shortcuts import get_object_or_404
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
            # Конвертируем из UTC в московское время
            local_time = timezone.localtime(last_transaction.punch_time)
            return local_time.strftime('%d.%m.%Y %H:%M')
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
    list_display = [
        'terminal_alias',
        'terminal_sn',
        'area_alias',
        'is_monitored',
        'currently_on_site_count',
        'transaction_count'
    ]
    list_filter = ['is_monitored', 'area_alias']
    search_fields = ['terminal_alias', 'terminal_sn', 'area_alias']

    def transaction_count(self, obj):
        count = Transaction.objects.filter(terminal=obj).count()
        url = f'/admin/bot/transaction/?terminal__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)

    transaction_count.short_description = 'Всего записей'

    def get_on_site_info(self, terminal):
        """Возвращает список сотрудников на пункте и их количество"""
        from django.utils import timezone
        from datetime import datetime, time

        today = timezone.now().date()
        today_start = timezone.make_aware(datetime.combine(today, time.min))
        today_end = timezone.make_aware(datetime.combine(today, time.max))

        # 1. Получаем ВСЕ события за сегодня для этого терминала
        events_today = Transaction.objects.filter(
            terminal=terminal,
            punch_time__range=[today_start, today_end]
        ).order_by('emp_code', 'punch_time')

        # 2. Группируем по emp_code
        events_by_emp = {}
        for event in events_today:
            emp_code = event.emp_code
            if emp_code not in events_by_emp:
                events_by_emp[emp_code] = []
            events_by_emp[emp_code].append(event)

        # 3. Определяем кто на пункте (алгоритм со стеком)
        on_site_list = []
        for emp_code, events in events_by_emp.items():
            stack = []  # стек для входов без выхода
            last_entry = None

            for event in events:
                if event.is_entry:  # вход
                    stack.append(event)
                    last_entry = event
                else:  # выход
                    if stack:
                        stack.pop()  # убираем последний несбалансированный вход

            # Если остались входы без выхода - сотрудник на пункте
            if stack:
                # Берем последний вход (самый поздний)
                last_entry = stack[-1]
                on_site_list.append({
                    'emp_code': emp_code,
                    'entry_time': last_entry.punch_time,
                    'employee': last_entry.employee,
                    'transaction': last_entry
                })

        return on_site_list

    def _get_on_site_count(self, terminal):
        """Подсчитать сколько человек на пункте (включая неизвестных)"""
        on_site_list = self.get_on_site_info(terminal)
        return len(on_site_list)

    def currently_on_site_count(self, obj):
        """Количество сотрудников на пункте - кликабельное число"""
        count = self._get_on_site_count(obj)

        if count == 0:
            return format_html('<span style="color: gray;">0</span>')

        # Ссылка на детальную страницу
        url = f'/admin/bot/terminal/{obj.id}/on_site/'
        return format_html('<a href="{}" title="Нажмите для просмотра списка">{}</a>', url, count)

    currently_on_site_count.short_description = 'На пункте'

    def get_urls(self):
        """Добавляем URL для детальной страницы"""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/on_site/',
                self.admin_site.admin_view(self.on_site_view),
                name='terminal_on_site',
            ),
        ]
        return custom_urls + urls

    def on_site_view(self, request, object_id):
        """Страница со списком сотрудников на пункте (включая неизвестных)"""
        from django.utils import timezone
        from datetime import datetime, time
        from django.shortcuts import render, get_object_or_404

        terminal = get_object_or_404(Terminal, id=object_id)

        # Используем общую функцию
        on_site_list_data = self.get_on_site_info(terminal)

        # Преобразуем в формат для шаблона
        on_site_list = []
        for item in on_site_list_data:
            on_site_list.append({
                'emp_code': item['emp_code'],
                'entry_time': item['entry_time'],
                'employee': item['employee'],
                'transaction': item['transaction']
            })

        context = {
            'terminal': terminal,
            'on_site_list': on_site_list,
            'today': timezone.now().date().strftime('%d.%m.%Y'),
            'current_time': timezone.now().strftime('%H:%M'),
        }

        return render(request, 'admin/terminal_on_site.html', context)

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