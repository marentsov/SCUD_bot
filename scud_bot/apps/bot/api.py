import json
import datetime
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
import logging

from .services.autologger import AutoLogger

logger = logging.getLogger(__name__)


def _fetch_scud_data(url, params, session_cookie, max_retries=2):
    """ Утилита для запросов к СКУД с автополучением куки """
    for attempt in range(max_retries):
        try:
            cookies = {'sessionid': session_cookie}

            response = requests.get(
                url,
                params=params,
                cookies=cookies,
                timeout=30
            )

            # успех
            if response.status_code == 200:
                return response

            # сессия умерла - обновляем куку
            if response.status_code == 401 and attempt < max_retries - 1:
                logger.info("Сессия истекла, получаем новую куку...")

                base_url = settings.SKUD_CONFIG['BASE_URL']
                autologger = AutoLogger(base_url=base_url)
                new_cookie = autologger.get_new_cookie()

                if new_cookie:
                    session_cookie = new_cookie
                    logger.info("Кука обновлена")
                    continue
                else:
                    raise Exception("Не удалось получить новую куку")

            # другие ошибки - сразу падаем
            response.raise_for_status()

        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                logger.warning(f"Ошибка запроса, пробуем снова: {e}")
                continue
            raise

    raise Exception("Все попытки запроса исчерпаны")


@csrf_exempt
def json_report(request):
    """ API для получения JSON отчета из СКУД системы """
    try:
        base_url = settings.SKUD_CONFIG['BASE_URL']
        session_cookie = settings.SKUD_CONFIG['SESSION_COOKIE']

        if not session_cookie:
            return JsonResponse({
                'error': 'Кука не настроена',
                'code': 500
            }, status=500)

        url = f"{base_url}/iclock/api/transactions/"
        params = {
            'format': request.GET.get('format', 'json'),
            'page_size': request.GET.get('page_size', 1000),
            'ordering': request.GET.get('ordering', '-id'),
        }

        response = _fetch_scud_data(url, params, session_cookie)
        data = response.json()

        return JsonResponse({
            'success': True,
            'data': data.get('data', []),
            'count': data.get('count', 0),
            'timestamp': timezone.now().isoformat(),
        })

    except Exception as e:
        logger.error(f"Ошибка json_report: {e}")
        return JsonResponse({
            'error': str(e),
            'code': 500
        }, status=500)


@csrf_exempt
def download_backup(request):
    """ Скачать полный бэкап как файл """
    try:
        base_url = settings.SKUD_CONFIG['BASE_URL']
        session_cookie = settings.SKUD_CONFIG['SESSION_COOKIE']

        if not session_cookie:
            return HttpResponse('Кука не настроена', status=500)

        url = f"{base_url}/iclock/api/transactions/"
        params = {
            'format': 'json',
            'page_size': 10000,
            'ordering': '-id',
        }

        response = _fetch_scud_data(url, params, session_cookie, max_retries=3)
        data = response.json()

        filename = f"sсud_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        http_response = HttpResponse(
            json.dumps(data, ensure_ascii=False, indent=2),
            content_type='application/octet-stream'
        )
        http_response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return http_response

    except Exception as e:
        logger.error(f"Ошибка download_backup: {e}")
        return JsonResponse({
            'error': str(e),
            'code': 500
        }, status=500)
