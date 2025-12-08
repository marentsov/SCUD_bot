import requests
import time
import logging
from typing import Optional, List
from django.conf import settings
from django.utils import timezone
from datetime import datetime

from ..models import Employee, Terminal, Transaction
from .bot import TelegramBot

logger = logging.getLogger(__name__)


class SKUDMonitor:
    """Класс для мониторинга СКУД"""

    def __init__(self):
        self.base_url = settings.SKUD_CONFIG['BASE_URL']
        self.session_cookie = settings.SKUD_CONFIG['SESSION_COOKIE']
        self.last_id = 0

        # Кэш
        self.employees_by_code = {}
        self.all_terminals_by_id = {}
        self.monitored_terminals = {}

        self._load_cache()

    def _load_cache(self):
        """Загружаем сотрудников и терминалы в память"""
        # Сотрудники по коду
        for emp in Employee.objects.all():
            self.employees_by_code[emp.emp_code] = emp

        # Все терминалы
        for term in Terminal.objects.all():
            self.all_terminals_by_id[term.terminal_id] = term
            if term.is_monitored:
                self.monitored_terminals[term.terminal_id] = term

        monitored_count = len(self.monitored_terminals)
        total_count = len(self.all_terminals_by_id)

        logger.info(f"Загружено {len(self.employees_by_code)} сотрудников")
        logger.info(f"Терминалов: {monitored_count} отслеживаемых из {total_count} всего")

        if monitored_count > 0:
            logger.info("Отслеживаемые терминалы:")
            for term in self.monitored_terminals.values():
                logger.info(f"   - {term.terminal_alias} (ID: {term.terminal_id})")

    def _get_employee(self, emp_code: str) -> Optional[Employee]:
        """Найти сотрудника по коду"""
        return self.employees_by_code.get(emp_code)

    def _should_process_terminal(self, terminal_id: int) -> bool:
        """Нужно ли обрабатывать этот терминал?"""
        if self.monitored_terminals:
            return terminal_id in self.monitored_terminals
        return True

    def _get_terminal_or_create(self, skud_data: dict) -> Optional[Terminal]:
        """Получить или создать терминал"""
        terminal_id = skud_data.get('terminal')

        # Если терминал уже в базе
        if terminal_id in self.all_terminals_by_id:
            return self.all_terminals_by_id[terminal_id]

        # Создаем новый
        try:
            terminal = Terminal.objects.create(
                terminal_id=terminal_id,
                terminal_sn=skud_data.get('terminal_sn', ''),
                terminal_alias=skud_data.get('terminal_alias', 'Неизвестный'),
                area_alias=skud_data.get('area_alias', ''),
                is_monitored=False
            )

            self.all_terminals_by_id[terminal_id] = terminal
            logger.info(f"🆕 Создан терминал: {terminal.terminal_alias} (ID: {terminal_id})")
            return terminal

        except Exception as e:
            logger.error(f"Ошибка создания терминала: {e}")
            return None

    def fetch_new_transactions(self) -> List[dict]:
        """Получить новые транзакции"""
        url = f"{self.base_url}/iclock/api/transactions/"

        params = {
            'format': 'json',
            'ordering': '-id',
            'page_size': 50,
        }

        headers = {}
        if self.session_cookie:
            headers['Cookie'] = f'sessionid={self.session_cookie}'

        try:
            logger.debug(f"Запрос к {url}")
            response = requests.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()

            new_transactions = []
            for item in data.get('data', []):
                if item['id'] > self.last_id:
                    self.last_id = item['id']
                    new_transactions.append(item)

            return new_transactions

        except Exception as e:
            logger.error(f"Ошибка запроса: {e}")
            return []

    def process_transaction(self, skud_data: dict):
        """Обработать одну транзакцию"""
        trans_id = skud_data.get('id')
        emp_code = skud_data.get('emp_code')
        terminal_id = skud_data.get('terminal')
        punch_time = skud_data.get('punch_time', '')[:19]
        action = 'ВХОД' if skud_data.get('punch_state') in ['0', 'I'] else 'ВЫХОД'

        logger.info(f"Обработка ID {trans_id}: сотр. {emp_code}, терм. {terminal_id}, {action} в {punch_time}")

        # Проверяем терминал
        if not self._should_process_terminal(terminal_id):
            logger.debug(f"Пропуск терминала {terminal_id}")
            return

        # Ищем сотрудника
        employee = self._get_employee(emp_code)
        if not employee:
            logger.warning(f"Сотрудник {emp_code} не найден")
            return

        # Получаем терминал
        terminal = self._get_terminal_or_create(skud_data)
        if not terminal:
            logger.error(f"Не удалось получить терминал {terminal_id}")
            return

        # Проверяем дубликат
        if Transaction.objects.filter(skud_id=trans_id).exists():
            logger.debug(f"Дубликат ID {trans_id}, пропускаем")
            return
        punch_time_str = skud_data['punch_time']
        try:
            # Создаем naive datetime
            naive_dt = datetime.strptime(punch_time_str, "%Y-%m-%d %H:%M:%S")
            # Делаем aware (с часовым поясом)
            aware_dt = timezone.make_aware(naive_dt, timezone.get_current_timezone())
        except:
            # Если ошибка - используем текущее время
            aware_dt = timezone.now()
            logger.warning(f"Не удалось распарсить время '{punch_time_str}', использую текущее")

        # Сохраняем транзакцию
        try:
            transaction = Transaction.objects.create(
                skud_id=trans_id,
                employee=employee,
                terminal=terminal,
                punch_time=aware_dt,  # ← ИСПОЛЬЗУЕМ aware datetime
                punch_state=skud_data['punch_state'],
                verify_type=skud_data['verify_type'],
            )

            # Краткий лог
            logger.info(
                f"СОХРАНЕНО: ID {trans_id} | Сотр. {emp_code} | {terminal.terminal_alias} | {action} | {punch_time[11:16]}")

            # Уведомления - ДОБАВИМ ЛОГИ ДЛЯ ОТЛАДКИ
            logger.info(f"[УВЕДОМЛЕНИЕ] Проверка условий:")
            logger.info(f"  - can_receive_notifications: {employee.can_receive_notifications}")
            logger.info(f"  - is_monitored: {terminal.is_monitored}")
            logger.info(f"  - telegram_id: {employee.telegram_id}")

            if employee.can_receive_notifications and terminal.is_monitored:
                logger.info(f"[УВЕДОМЛЕНИЕ] Условия выполнены, отправляю...")
                self._send_notification(employee, transaction)
            else:
                logger.info(f"[УВЕДОМЛЕНИЕ] Условия НЕ выполнены, пропускаю")

        except Exception as e:
            logger.error(f"Ошибка сохранения ID {trans_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())

    # def process_transaction(self, skud_data: dict):
    #     """Обработать одну транзакцию"""
    #     trans_id = skud_data.get('id')
    #     emp_code = skud_data.get('emp_code')
    #     terminal_id = skud_data.get('terminal')
    #     punch_time = skud_data.get('punch_time', '')[:19]
    #     action = 'ВХОД' if skud_data.get('punch_state') in ['0', 'I'] else 'ВЫХОД'
    #
    #     logger.info(f"Обработка ID {trans_id}: сотр. {emp_code}, терм. {terminal_id}, {action} в {punch_time}")
    #
    #     # Проверяем терминал
    #     if not self._should_process_terminal(terminal_id):
    #         logger.debug(f"Пропуск терминала {terminal_id}")
    #         return
    #
    #     # Ищем сотрудника
    #     employee = self._get_employee(emp_code)
    #     if not employee:
    #         logger.warning(f"Сотрудник {emp_code} не найден")
    #         return
    #
    #     # Получаем терминал
    #     terminal = self._get_terminal_or_create(skud_data)
    #     if not terminal:
    #         logger.error(f"Не удалось получить терминал {terminal_id}")
    #         return
    #
    #     # Проверяем дубликат
    #     if Transaction.objects.filter(skud_id=trans_id).exists():
    #         logger.debug(f"Дубликат ID {trans_id}, пропускаем")
    #         return
    #     punch_time_str = skud_data['punch_time']
    #     try:
    #         # Создаем naive datetime
    #         naive_dt = datetime.strptime(punch_time_str, "%Y-%m-%d %H:%M:%S")
    #         # Делаем aware (с часовым поясом)
    #         aware_dt = timezone.make_aware(naive_dt, timezone.get_current_timezone())
    #     except:
    #         # Если ошибка - используем текущее время
    #         aware_dt = timezone.now()
    #         logger.warning(f"Не удалось распарсить время '{punch_time_str}', использую текущее")
    #
    #     # Сохраняем транзакцию
    #     try:
    #         transaction = Transaction.objects.create(
    #             skud_id=trans_id,
    #             employee=employee,
    #             terminal=terminal,
    #             punch_time=aware_dt,  # ← ИСПОЛЬЗУЕМ aware datetime
    #             punch_state=skud_data['punch_state'],
    #             verify_type=skud_data['verify_type'],
    #         )
    #
    #         # Краткий лог
    #         logger.info(
    #             f"СОХРАНЕНО: ID {trans_id} | Сотр. {emp_code} | {terminal.terminal_alias} | {action} | {punch_time[11:16]}")
    #
    #         # Уведомления
    #         if employee.can_receive_notifications and terminal.is_monitored:
    #             self._send_notification(employee, transaction)
    #
    #     except Exception as e:
    #         logger.error(f"Ошибка сохранения ID {trans_id}: {e}")
    #         import traceback
    #         logger.error(traceback.format_exc())

    def _send_notification(self, employee: Employee, transaction: Transaction):
        """Отправить уведомление"""
        try:

            action = "вход" if transaction.is_entry else "выход"
            location = transaction.terminal.terminal_alias
            time_str = transaction.punch_time.strftime('%H:%M')
            date_str = transaction.punch_time.strftime('%d.%m.%Y')

            message = (
                f"СКУД Уведомление\n\n"
                f"{employee.name}\n"
                f"{location}\n"
                f"{date_str}\n"
                f"{time_str}\n"
                f"{action.upper()}"
            )

            # отправляем через бота
            bot = TelegramBot()
            success = bot.send_message(employee.telegram_id, message)

            if success:
                logger.info(f"Уведомление отправлено {employee.name}")
            else:
                logger.warning(f"Не удалось отправить уведомление {employee.name}")

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления - {e}")

    def run(self):
        """Запуск мониторинга"""
        logger.info("МОНИТОРИНГ СКУД ЗАПУЩЕН")
        logger.info("=" * 60)

        while True:
            try:
                # Получаем новые транзакции
                new_transactions = self.fetch_new_transactions()

                if new_transactions:
                    logger.info(f"Получено {len(new_transactions)} новых записей")

                    for i, data in enumerate(new_transactions):
                        logger.debug(f"  {i + 1}. ID {data.get('id')} - {data.get('emp_code')}")
                        self.process_transaction(data)
                else:
                    logger.debug("Нет новых записей")

                time.sleep(settings.SKUD_CONFIG['POLL_INTERVAL'])

            except KeyboardInterrupt:
                logger.info("Мониторинг остановлен")
                break
            except Exception as e:
                logger.error(f"Критическая ошибка: {e}")
                time.sleep(30)