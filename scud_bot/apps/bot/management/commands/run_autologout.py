import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime

from ...services.autologout import AutoLogoutService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Запуск автоматического выхода сотрудников в 23:55'

    def add_arguments(self, parser):
        parser.add_argument(
            '--time',
            type=str,
            help='Время выхода в формате ГГГГ-ММ-ДД ЧЧ:ММ:СС (по умолчанию сейчас)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать кто будет выписан без реальной отправки'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Выполнить выход даже не в 23:50-23:59'
        )

    def handle(self, *args, **options):
        logger.info("ЗАПУСК АВТОМАТИЧЕСКОГО ВЫХОДА СОТРУДНИКОВ")


        # Определяем время выхода
        if options['time']:
            try:
                naive_dt = datetime.strptime(options['time'], '%Y-%m-%d %H:%M:%S')
                target_time = timezone.make_aware(naive_dt)
            except ValueError:
                self.stderr.write(f"Неверный формат времени. Используйте: ГГГГ-ММ-ДД ЧЧ:ММ:СС")
                return
        else:
            target_time = timezone.now()

        self.stdout.write(f"Время выхода - {target_time.strftime('%d.%m.%Y %H:%M:%S')}")

        # Проверяем время (если не форс-режим)
        if not options['force']:
            current_hour = target_time.hour
            current_minute = target_time.minute

            if not (current_hour == 18 and current_minute == 7):
                self.stdout.write(
                    "Внимание: сейчас не время автоматического выхода (23:40-23:59)\n"
                    "Используйте --force для принудительного выполнения"
                )
                return

        # Создаем сервис
        service = AutoLogoutService()

        # Получаем список сотрудников на пункте
        on_site_employees = service.get_employees_on_site_today(target_time.date())

        if not on_site_employees:
            self.stdout.write(" Нет сотрудников для автоматического выхода")
            return

        # Выводим информацию
        self.stdout.write(f"\n Найдено {len(on_site_employees)} сотрудников на пункте:")
        for i, item in enumerate(on_site_employees, 1):
            employee = item['employee']
            terminal = item['terminal']
            entry_time = timezone.localtime(item['entry_time'])

            self.stdout.write(
                f"{i}. {employee.name} ({employee.emp_code}) - "
                f"вошел в {entry_time.strftime('%H:%M')} на {terminal.terminal_alias}"
            )

        # Dry run режим
        if options['dry_run']:
            self.stdout.write(f"\n Dry run завершен: {len(on_site_employees)} сотрудников будут выписаны")
            return

        # Запрашиваем подтверждение
        confirm = input(f"\nВыполнить выход для {len(on_site_employees)} сотрудников? (y/N): ")

        if confirm.lower() != 'y':
            self.stdout.write("Отменено")
            return

        # Выполняем выход
        self.stdout.write("\n Выполняю автоматический выход...")

        results = service.perform_auto_logout(target_time)

        if results:
            # Выводим результаты
            self.stdout.write("\n Результаты:")

            successful = 0
            for result in results:
                employee = result['employee']
                terminal = result['terminal']

                if result['logout_success']:
                    successful += 1
                    self.stdout.write(f"  {employee.name}: успешно выписан с {terminal.terminal_alias}")
                else:
                    self.stdout.write(f"  {employee.name}: ошибка - {result['logout_message']}")

            self.stdout.write(f"\n Итог: {successful} из {len(results)} успешно выписаны")
        else:
            self.stdout.write("\n Нет результатов выполнения")