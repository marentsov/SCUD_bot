import logging
import requests
from datetime import datetime, time as time_type, timedelta
from django.utils import timezone
from django.conf import settings
from django.db.models import Q

from ..models import Employee, Transaction, Terminal

logger = logging.getLogger(__name__)


class AutoLogoutService:
    """Сервис для автоматического выхода сотрудников в 23:55"""

    def __init__(self):
        self.base_url = settings.SKUD_CONFIG['BASE_URL']
        self.headers = {
            "Host": "http",
            "User-Agent": "iClock Proxy/1.09",
            "Connection": "close",
            "Accept": "*/*",
            "Content-Type": "text/plain;charset=UTF-8",
        }

    def get_employees_on_site_today(self, target_date=None):
        """
        Получить список сотрудников, которые остались на пункте сегодня

        Сотрудник считается на пункте если:
        1. У него есть запись ВХОД за сегодня
        2. Нет записи ВЫХОД после последнего входа
        3. Последняя запись за сегодня - ВХОД
        """
        if target_date is None:
            target_date = timezone.now().date()

        # Начало и конец дня (по московскому времени)
        day_start = timezone.make_aware(datetime.combine(target_date, time_type.min))
        day_end = timezone.make_aware(datetime.combine(target_date, time_type.max))

        # Получаем всех сотрудников с активным автовыходом
        employees_with_auto_logout = Employee.objects.filter(auto_logout=True)

        on_site_employees = []

        for employee in employees_with_auto_logout:
            # Получаем все транзакции сотрудника за сегодня
            transactions_today = Transaction.objects.filter(
                Q(employee=employee) | Q(emp_code=employee.emp_code),
                punch_time__range=[day_start, day_end]
            ).order_by('punch_time')

            if not transactions_today.exists():
                continue  # Сотрудник не был сегодня на пункте

            # Находим последнюю транзакцию за сегодня
            last_transaction = transactions_today.last()

            # Если последняя транзакция - ВХОД, сотрудник на пункте
            if last_transaction.is_entry:
                # Ищем терминал последнего входа
                terminal = last_transaction.terminal

                on_site_employees.append({
                    'employee': employee,
                    'last_entry': last_transaction,
                    'terminal': terminal,
                    'entry_time': last_transaction.punch_time,
                })

        return on_site_employees

    def create_logout_request(self, employee, terminal, logout_time):
        """
        Создать запрос на выход в формате СКУД

        Формат данных:
        {emp_id}\t{timestamp}\t1\t1\t0\t0\t0\t0\t0\t0\t661\n
        """
        # Форматируем время для СКУД
        timestamp_str = logout_time.strftime('%Y-%m-%d %H:%M:%S')

        # Формируем URL с серийным номером терминала
        url = f"{self.base_url}/iclock/cdata?SN={terminal.terminal_sn}&table=ATTLOG&Stamp=9999"

        # Формируем тело запроса (точно как в ручных выходах)
        data = f"{employee.emp_id}\t{timestamp_str}\t1\t1\t0\t0\t0\t0\t0\t0\t661\n"

        return url, data.encode('utf-8')

    def send_logout_request(self, url, data):
        """Отправить запрос на выход в СКУД"""
        try:
            logger.debug(f"Отправка запроса на {url}")
            logger.debug(f"Данные: {data.decode('utf-8').strip()}")

            response = requests.post(
                url,
                data=data,
                headers=self.headers,
                timeout=15
            )

            logger.info(f"Ответ СКУД: статус {response.status_code}")

            # Пробуем получить текст ответа
            try:
                response_text = response.text
                logger.info(f"Текст ответа: {response_text}")
            except UnicodeDecodeError:
                # Если ответ бинарный, выводим hex
                logger.info(f"Бинарный ответ: {response.content.hex()}")
                response_text = "binary_response"

            # Проверяем успешный ответ (часто СКУД возвращает OK или пустой ответ)
            if response.status_code == 200:
                # Проверяем содержимое ответа
                if "OK" in response_text or response_text.strip() == "" or "success" in response_text.lower():
                    return True, response_text
                else:
                    logger.warning(f"Странный ответ от СКУД: {response_text}")
                    return False, f"Unexpected response: {response_text}"
            else:
                return False, f"HTTP {response.status_code}: {response_text}"

        except requests.Timeout:
            logger.error("Таймаут при отправке запроса на выход")
            return False, "Request timed out"
        except requests.RequestException as e:
            logger.error(f"Ошибка сети при отправке запроса - {e}")
            return False, f"Network error: {str(e)}"
        except Exception as e:
            logger.error(f"Ошибка при отправке запроса - {e}")
            return False, str(e)

    def create_local_logout_record(self, employee, terminal, logout_time):
        """
        Создать локальную запись о выходе в базе данных

        Эта запись будет идентична обычным выходам, только verify_type=99
        """
        try:
            # Создаем запись транзакции
            transaction = Transaction.objects.create(
                skud_id=0,  # Временный ID, т.к. создается через API
                employee=employee,
                emp_code=employee.emp_code,
                terminal=terminal,
                punch_time=logout_time,
                punch_state='1',  # Выход
                verify_type=99,  # Специальный код для автовыхода
            )

            logger.info(f"Создана локальная запись выхода для {employee.name}")
            return transaction

        except Exception as e:
            logger.error(f"Ошибка создания локальной записи: {e}")
            return None

    def perform_auto_logout(self, target_time=None):
        """
        Выполнить автоматический выход для всех сотрудников на пункте

        Args:
            target_time: Время выхода (по умолчанию текущее время)
        """
        if target_time is None:
            target_time = timezone.now()


        logger.info(f" ЗАПУСК АВТОМАТИЧЕСКОГО ВЫХОДА - ({target_time})")


        # Получаем сотрудников на пункте сегодня
        on_site_employees = self.get_employees_on_site_today(target_time.date())

        if not on_site_employees:
            logger.info("Нет сотрудников для автоматического выхода")
            return []

        logger.info(f"Найдено {len(on_site_employees)} сотрудников на пункте:")

        results = []

        for item in on_site_employees:
            employee = item['employee']
            terminal = item['terminal']
            entry_time = item['entry_time']

            logger.info(
                f"  - {employee.name} ({employee.emp_code}) вошел в {entry_time.strftime('%H:%M')} на {terminal.terminal_alias}")

        # Выполняем выход для каждого сотрудника
        for item in on_site_employees:
            employee = item['employee']
            terminal = item['terminal']
            entry_time = item['entry_time']

            # Используем заданное время выхода
            logout_time = target_time

            logger.info(f"Выход для {employee.name} с {terminal.terminal_alias} в {logout_time.strftime('%H:%M')}")

            # 1. Отправляем запрос в СКУД
            url, data = self.create_logout_request(employee, terminal, logout_time)
            success, message = self.send_logout_request(url, data)

            # 2. Создаем локальную запись (даже если запрос к СКУД не удался)
            local_record = self.create_local_logout_record(employee, terminal, logout_time)

            result = {
                'employee': employee,
                'terminal': terminal,
                'entry_time': entry_time,
                'logout_time': logout_time,
                'logout_success': success,
                'logout_message': message,
                'local_record_created': local_record is not None,
            }

            results.append(result)

            if success:
                logger.info(f" {employee.name} успешно выписан с {terminal.terminal_alias}")
            else:
                logger.warning(f" {employee.name}: ошибка выписки - {message}")

        # Сводка
        successful = sum(1 for r in results if r['logout_success'])
        logger.info(f"Итог: {successful} из {len(results)} сотрудников выписаны успешно")

        return results

    def run_daily_auto_logout(self):
        """
        Запуск ежедневного автоматического выхода

        Эта функция будет вызываться по расписанию в 23:50
        """
        now = timezone.now()
        logger.info(f" Запуск ежедневного автовыхода в {now.strftime('%H:%M')}")

        # Проверяем что время примерно 23:50 (допуск ±10 минут)
        current_hour = now.hour
        current_minute = now.minute

        msk_now = timezone.localtime(now)
        if msk_now.hour == 11 and msk_now.minute == 32:
            logger.info(" Время для автовыхода (23:40-23:59)")
            return self.perform_auto_logout(now)
        else:
            logger.warning(f" Неподходящее время для автовыхода: {current_hour:02d}:{current_minute:02d}")
            return []