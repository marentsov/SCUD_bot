import logging
from django.core.management.base import BaseCommand
from django.conf import settings

from ...services.monitor import SKUDMonitor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('skud_monitor_detailed.log')
    ]
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Запуск мониторинга СКУД системы'

    def handle(self, *args, **options):
        logger.info("=" * 60)
        logger.info("ЗАПУСК МОНИТОРИНГА СКУД")
        logger.info("=" * 60)

        # Проверяем настройки
        if not settings.SKUD_CONFIG.get('SESSION_COOKIE'):
            logger.error("❌ Не настроен SESSION_COOKIE в settings.py")
            return

        logger.info(f"🌐 URL: {settings.SKUD_CONFIG['BASE_URL']}")
        logger.info(f"⏱️ Интервал: {settings.SKUD_CONFIG['POLL_INTERVAL']} сек")

        # Создаем и запускаем монитор
        monitor = SKUDMonitor()

        try:
            monitor.run()
        except KeyboardInterrupt:
            logger.info("🛑 Мониторинг остановлен пользователем")
        except Exception as e:
            logger.error(f"💥 Ошибка запуска: {e}")