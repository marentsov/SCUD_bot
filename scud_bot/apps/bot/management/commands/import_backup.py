import json
import os
from pathlib import Path
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from ...models import Transaction, Employee, Terminal


class Command(BaseCommand):
    help = 'Импорт данных из JSON бэкапов СКУД'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Путь к JSON файлу бэкапа'
        )
        parser.add_argument(
            '--skip_existing',  # ← ИСПРАВЛЕНО: подчеркивание вместо дефиса
            action='store_true',
            help='Пропускать уже существующие записи (по skud_id)'
        )

    def handle(self, *args, **options):
        file_path = Path(options['file'])
        skip_existing = options['skip_existing']  # ← ИСПРАВЛЕНО здесь тоже

        if not file_path.exists():
            self.stderr.write(f"Файл не найден: {file_path}")
            return

        self.stdout.write(f"Чтение файла: {file_path.name}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.stderr.write(f"Ошибка чтения JSON: {e}")
            return

        if 'data' not in data:
            self.stderr.write("Файл не содержит ключ 'data'")
            return

        transactions_data = data['data']
        total = len(transactions_data)

        self.stdout.write(f"Найдено {total} записей")
        self.stdout.write(f"Пропускать существующие: {'Да' if skip_existing else 'Нет'}")

        # Подготовка кэшей
        existing_transactions = set(
            Transaction.objects.values_list('skud_id', flat=True)
        ) if skip_existing else set()

        employees_by_code = {
            e.emp_code: e for e in Employee.objects.all()
        }

        terminals_by_id = {}
        for term in Terminal.objects.all():
            terminals_by_id[term.terminal_id] = term

        imported = 0
        skipped = 0
        errors = 0

        for i, item in enumerate(transactions_data):
            if i % 1000 == 0:
                self.stdout.write(f"Обработано {i}/{total}...")

            skud_id = item.get('id')
            if not skud_id:
                errors += 1
                continue

            if skip_existing and skud_id in existing_transactions:
                skipped += 1
                continue

            emp_code = item.get('emp_code', '')
            terminal_id = item.get('terminal')

            # Ищем сотрудника
            employee = employees_by_code.get(emp_code)

            # Получаем или создаем терминал
            terminal = terminals_by_id.get(terminal_id)
            if not terminal and terminal_id is not None:
                try:
                    terminal = Terminal.objects.create(
                        terminal_id=terminal_id,
                        terminal_sn=item.get('terminal_sn', ''),
                        terminal_alias=item.get('terminal_alias', f'Терминал {terminal_id}'),
                        area_alias=item.get('area_alias', ''),
                        is_monitored=False
                    )
                    terminals_by_id[terminal_id] = terminal
                except Exception as e:
                    self.stderr.write(f"Ошибка создания терминала {terminal_id}: {e}")
                    errors += 1
                    continue

            # Парсим время
            punch_time_str = item.get('punch_time')
            try:
                naive_dt = datetime.strptime(punch_time_str, "%Y-%m-%d %H:%M:%S")
                aware_dt = timezone.make_aware(naive_dt, timezone.get_current_timezone())
            except:
                aware_dt = timezone.now()

            # Создаем транзакцию
            try:
                Transaction.objects.create(
                    skud_id=skud_id,
                    employee=employee,
                    emp_code=emp_code,
                    terminal=terminal,
                    punch_time=aware_dt,
                    punch_state=item.get('punch_state', '0'),
                    verify_type=item.get('verify_type', 1),
                )
                imported += 1

            except Exception as e:
                errors += 1
                if 'duplicate' in str(e).lower() or 'unique' in str(e).lower():
                    skipped += 1
                else:
                    self.stderr.write(f"Ошибка записи ID {skud_id}: {e}")

        self.stdout.write(f"Всего записей в файле: {total}")
        self.stdout.write(f"Импортировано: {imported}")
        self.stdout.write(f"Пропущено: {skipped}")
        self.stdout.write(f"Ошибок: {errors}")
