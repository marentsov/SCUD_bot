import os
from celery import Celery
from celery.schedules import crontab

# Django settings модуль для celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scud_bot.config.settings')

app = Celery('scud_bot')

# настройки Django
app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

# Настройки расписания
app.conf.beat_schedule = {
    'auto-logout-daily-2350': {
        'task': 'scud_bot.apps.bot.tasks.daily_auto_logout',
        'schedule': crontab(hour=18, minute=7),
        'args': (),
    },
}

app.conf.timezone = 'Europe/Moscow'