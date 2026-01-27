import logging
from celery import shared_task
from django.utils import timezone
from .services.autologout import AutoLogoutService

logger = logging.getLogger(__name__)


@shared_task
def daily_auto_logout():
    """Ежедневная задача автоматического выхода в 23:50"""
    logger.info("Запуск ежедневного автовыхода по расписанию")

    try:
        service = AutoLogoutService()
        results = service.run_daily_auto_logout()

        if results:
            successful = sum(1 for r in results if r['logout_success'])
            total = len(results)

            logger.info(f"Автовыход завершен -  {successful}/{total} успешно")

            return {
                'success': True,
                'processed': total,
                'successful': successful,
                'timestamp': timezone.now().isoformat(),
            }
        else:
            logger.info("Нет сотрудников для автовыхода")

            return {
                'success': True,
                'processed': 0,
                'successful': 0,
                'timestamp': timezone.now().isoformat(),
            }

    except Exception as e:
        logger.error(f"Ошибка в задаче автовыхода - {e}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat(),
        }


@shared_task
def test_auto_logout():
    """Тестовая задача для проверки автовыхода"""
    logger.info("Тестовая задача автовыхода")

    service = AutoLogoutService()

    # Получаем список кто на пункте
    on_site = service.get_employees_on_site_today()

    return {
        'on_site_count': len(on_site),
        'employees': [
            {
                'name': data['employee'].name,
                'emp_code': data['employee'].emp_code,
                'terminal': data['terminal'].terminal_alias,
                'entry_time': data['entry_time'].isoformat(),
            }
            for data in on_site
        ]
    }