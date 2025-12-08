import logging
import requests
import time
from typing import Optional, Tuple
from django.conf import settings


from ..models import Employee

logger = logging.getLogger(__name__)

class TelegramBot:
    """Телеграм бот для рассылки уведомлений о проходах"""

    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0


    def get_updates(self) -> list:
        """получение обновлений"""
        if not self.token:
            return []

        url = f"{self.base_url}/getUpdates"
        params = {
            'offset': self.offset,
            'timeout': 30,
        }

        try:
            response = requests.get(url, params=params, timeout=35)
            response.raise_for_status()
            data = response.json()

            if data.get('ok') and data.get('result'):
                updates = data['result']
                if updates:
                    self.offset = updates[-1]['update_id'] + 1
                return updates
            return []

        except Exception as e:
            logger.error(f"Ошибка получения обновлений - {e}")
            return []


    def send_message(self, chat_id: int, text: str) -> bool:
        """отправить сообщение"""
        if not self.token:
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения - {e}")
            return False


    def link_employee(self, telegram_id: int, telegram_username: str) -> Tuple[bool, str]:
        """функция-обработка привязки тг аккаунта к сотруднику"""

        try:
            username = telegram_username.lstrip('@')

            employee = Employee.objects.filter(
                telegram_username__iexact=username).first()

            if not employee:
                return False, (
                    "Вы не добавлены как сотрудник.\n"
                    "Обратитесь к администратору.\n\n"
                    f"Ваш юзернейм - @{username}"
                )

            if employee.telegram_id:
                if employee.telegram_id == telegram_id:
                    return False, "Ваш аккаунт уже привязан"
                else:
                    return False, "Этот юзернейм привязан к другому аккаунту"

            employee.telegram_id = telegram_id
            employee.telegram_username = username
            employee.send_notifications = True
            employee.save()

            logger.info(f"Telegram привязан: {employee.name} -> @{username}")

            return True, (
                "Успешно привязано!\n\n"
                f"Сотрудник: {employee.name}\n"
                f"Код сотрудника: {employee.emp_code}\n"
                f"Теперь вы будете получать уведомления о приходах"
            )

        except Exception as e:
            logger.error(f"Ошибка привязки - {e}")
            return False, f"Ошибка - {str(e)}"


    def handle_command(self, update: dict):
        """обработать команду из обновления"""
        message = update.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '').strip()
        username = message.get('from', {}).get('username', '')
        first_name = message.get('from', {}).get('first_name', '')


        if not chat_id or not text:
            return

        logger.info(f"Команда от @{username}: {text}")


        if text.lower() == '/start':
            welcome = (
                f"Привет я бот для уведомлений через СКУД\n\n"
            )

            if username:
                welcome += (
                    f"Ваш username: @{username}\n\n"
                    "Пытаюсь привязать ваш аккаунт к системе..."
                )
                self.send_message(chat_id, welcome)

                # Пытаемся привязать
                success, result_msg = self.link_employee(chat_id, username)
                self.send_message(chat_id, result_msg)

                if success:
                    # Дополнительная информация
                    info = (
                        "Вы будете получать уведомления вида:\n"
                        "[СКУД]\n"
                        "Ваше имя\n"
                        "Место прохода\n"
                        "Время\n"
                        "Вход/Выход\n\n"
                        "Для отключения - обратитесь к администратору."
                    )
                    self.send_message(chat_id, info)
            else:
                error_msg = (
                    "У вас не установлен username в Telegram.\n\n"
                    "Для работы с ботом необходимо:\n"
                    "1. Зайти в настройки Telegram\n"
                    "2. Установить username (имя пользователя)\n"
                    "3. Сообщить его администратору\n"
                    "4. Попробовать снова /start"
                )
                self.send_message(chat_id, error_msg)

        elif text.lower() == '/help':
            help_text = (
                "ℹПомощь:\n\n"
                "/start - Привязать аккаунт к системе\n"
                "/help - Эта справка\n\n"
                "Для привязки:\n"
                "1. Ваш username должен быть указан в системе\n"
                "2. Используйте команду /start\n"
                "3. Готово!\n\n"
                "Проблемы? Обратитесь к администратору."
            )
            self.send_message(chat_id, help_text)

        else:
            unknown_msg = (
                "Неизвестная команда.\n"
                "Используйте:\n"
                "/start - для начала работы\n"
                "/help - для справки"
            )
            self.send_message(chat_id, unknown_msg)


    def run(self):
        """запуск бота в пулинг режиме"""
        logger.info("🤖 Запуск Telegram бота...")

        # Проверяем токен
        if not self.token:
            logger.error("Токен бота не настроен!")
            return

        test_url = f"{self.base_url}/getMe"
        try:
            response = requests.get(test_url, timeout=10)
            if not response.json().get('ok'):
                logger.error("Неверный токен бота!")
                return
            bot_info = response.json().get('result', {})
            logger.info(f"Бот запущен: {bot_info.get('first_name')} (@{bot_info.get('username')})")
        except:
            logger.error("Ошибка подключения к Telegram API")
            return

        logger.info("Ожидание команд...")

        # Основной цикл
        while True:
            try:
                updates = self.get_updates()

                for update in updates:
                    self.handle_command(update)

                # Небольшая пауза между опросами
                time.sleep(settings.TELEGRAM_POLL_INTERVAL)

            except KeyboardInterrupt:
                logger.info("Бот остановлен")
                break
            except Exception as e:
                logger.error(f"Ошибка в основном цикле бота - {e}")
                time.sleep(5)




