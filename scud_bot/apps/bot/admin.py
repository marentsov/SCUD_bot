from django.contrib import admin
from django.utils.html import format_html
from .models import Terminal, Employee, Transaction


@admin.register(Terminal)
class TerminalAdmin(admin.ModelAdmin):
    list_display = ('terminal_alias', 'area_alias', 'terminal_id', 'is_monitored')
    search_fields = ('terminal_alias', 'area_alias')
    list_editable = ('is_monitored',)
    list_filter = ('is_monitored', 'area_alias')


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('emp_code', 'name', 'telegram_id', 'notification_status', 'send_notifications')
    search_fields = ('emp_code', 'name', 'telegram_username')
    list_editable = ('send_notifications',)

    def notification_status(self, obj):
        if not obj.telegram_id:
            return "Нет Telegram ID"
        if not obj.send_notifications:
            return "Уведомления выключены"
        return "Уведомления ВКЛ"

    # TODO создать филдсетс для отображения проходок сотрудников

    notification_status.short_description = "Уведомления"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('employee', 'terminal', 'punch_time', 'punch_state_display', 'verify_type_display')
    list_filter = ('punch_state', 'terminal', 'punch_time')
    search_fields = ('employee__emp_code', 'employee__name')

    def punch_state_display(self, obj):
        """стейт проходки"""
        if obj.punch_state in ['0', 'I']:
            return "Вход"
        elif obj.punch_state in ['1', 'O']:
            return "Выход"
        else:
            return obj.punch_state

    punch_state_display.short_description = "Действие"

    def verify_type_display(self, obj):
        """тип верификации"""
        verify_types = {
            0: 'Пароль',
            1: 'Отпечаток',
            4: 'Карта',
            15: 'Лицо',
        }
        return verify_types.get(obj.verify_type, f'Тип {obj.verify_type}')

    verify_type_display.short_description = "Способ"