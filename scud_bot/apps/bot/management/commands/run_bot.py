import logging
from django.core.management.base import BaseCommand
from ...services.bot import TelegramBot

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Запуск Telegram бота'

    def handle(self, *args, **options):
        logger.info("=" * 50)
        logger.info("🤖 ЗАПУСК TELEGRAM БОТА")
        logger.info("=" * 50)

        bot = TelegramBot()
        bot.run()