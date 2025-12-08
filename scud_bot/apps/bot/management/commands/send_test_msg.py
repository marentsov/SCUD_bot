import logging
from django.core.management.base import BaseCommand
from ...models import Employee
from ...services.bot import TelegramBot

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Отправить тестовое сообщение сотруднику'

    def add_arguments(self, parser):
        parser.add_argument('emp_code', type=str, help='Код сотрудника')

    def handle(self, *args, **options):
        emp_code = options['emp_code']

        try:
            employee = Employee.objects.get(emp_code=emp_code)

            self.stdout.write(f"Сотрудник: {employee.name}")
            self.stdout.write(f"Telegram ID: {employee.telegram_id}")
            self.stdout.write(f"Отправлять уведомления: {employee.send_notifications}")
            self.stdout.write(f"Может получать: {employee.can_receive_notifications}")

            if not employee.telegram_id:
                self.stdout.write(self.style.ERROR("У сотрудника нет Telegram ID"))
                return

            bot = TelegramBot()

            # Простое тестовое сообщение
            message = f"Тестовое сообщение от бота СКУД\n\n {employee.name}\n Бот работает!"

            self.stdout.write(f"Отправляю сообщение...")

            if bot.send_message(employee.telegram_id, message):
                self.stdout.write(self.style.SUCCESS("Сообщение отправлено!"))
            else:
                self.stdout.write(self.style.ERROR("Ошибка отправки"))

        except Employee.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Сотрудник с кодом {emp_code} не найден"))