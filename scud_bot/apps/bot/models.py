from django.db import models
from django.utils import timezone


class Terminal(models.Model):
    """Терминалы СКУД"""
    terminal_id = models.IntegerField(unique=True, verbose_name="ID терминала")
    terminal_sn = models.CharField(max_length=50, verbose_name="Серийный номер")
    terminal_alias = models.CharField(max_length=200, verbose_name="Название терминала")
    area_alias = models.CharField(max_length=200, verbose_name="Название зоны")
    is_monitored = models.BooleanField(default=True, verbose_name="Отслеживать терминал")

    class Meta:
        verbose_name = "Терминал"
        verbose_name_plural = "Терминалы"
        ordering = ['terminal_alias']

    def __str__(self):
        return f"{self.terminal_alias} ({self.terminal_sn})"


class Employee(models.Model):
    """Сотрудники"""
    emp_id = models.IntegerField(unique=True, verbose_name="ID сотрудника")
    emp_code = models.CharField(max_length=20, verbose_name="Код сотрудника")
    name = models.CharField(max_length=200, blank=True, verbose_name="Имя сотрудника")

    # Telegram
    telegram_id = models.BigIntegerField(null=True, blank=True, verbose_name="Telegram ID")
    telegram_username = models.CharField(max_length=100, blank=True, verbose_name="Telegram username")

    # Настройки уведомлений
    send_notifications = models.BooleanField(default=False, verbose_name="Отправлять уведомления")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        ordering = ['emp_code']

    def __str__(self):
        name = self.name if self.name else f"Сотр. {self.emp_code}"
        return f"{name} ({self.emp_code})"

    @property
    def can_receive_notifications(self):
        """Получает ли сотрудник уведомления?"""
        return self.send_notifications and self.telegram_id is not None


class Transaction(models.Model):
    """Записи проходок СКУД"""
    skud_id = models.IntegerField(unique=True, verbose_name="ID записи в СКУД")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name="Сотрудник")
    terminal = models.ForeignKey(Terminal, on_delete=models.CASCADE, verbose_name="Терминал")
    punch_time = models.DateTimeField(verbose_name="Время отметки")

    # 0 = вход, 1 = выход
    punch_state = models.CharField(max_length=5, verbose_name="Тип отметки")

    # 1 = отпечаток, 15 = лицо, 4 = карта
    verify_type = models.IntegerField(verbose_name="Способ авторизации")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Время создания")

    class Meta:
        verbose_name = "Запись прохода"
        verbose_name_plural = "Записи проходов"
        ordering = ['-punch_time']

    def __str__(self):
        action = "вход" if self.punch_state in ['0', 'I'] else "выход"
        return f"{self.employee} - {action} в {self.punch_time.strftime('%H:%M')}"

    @property
    def is_entry(self):
        """Вход?"""
        return self.punch_state in ['0', 'I']

    @property
    def is_exit(self):
        """Выход?"""
        return self.punch_state in ['1', 'O']