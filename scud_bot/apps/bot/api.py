import json
import datetime
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone


@csrf_exempt
def json_report(request):
    """
    API для получения JSON отчета из СКУД системы
    Доступно по: https://scud.smit.4gain.pro/api/json_report
    """
    try:
        # Получаем настройки из конфигурации
        base_url = settings.SKUD_CONFIG.get('BASE_URL', 'http://188.92.110.218')
        session_cookie = settings.SKUD_CONFIG.get('SESSION_COOKIE')

        if not session_cookie:
            return JsonResponse({
                'error': 'Сессионная кука не настроена',
                'code': 500
            }, status=500)

        # Параметры запроса из GET-параметров или по умолчанию
        page_size = request.GET.get('page_size', 1000)
        ordering = request.GET.get('ordering', '-id')
        format_type = request.GET.get('format', 'json')

        # Формируем URL
        url = f"{base_url}/iclock/api/transactions/"
        params = {
            'format': format_type,
            'page_size': page_size,
            'ordering': ordering,
        }

        # Куки
        cookies = {
            'sessionid': session_cookie
        }

        # Делаем запрос
        response = requests.get(url, params=params, cookies=cookies, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Возвращаем JSON
        return JsonResponse({
            'success': True,
            'data': data.get('data', []),
            'count': data.get('count', 0),
            'timestamp': timezone.now().isoformat(),
            'source_url': url,
            'parameters': params
        })

    except requests.exceptions.RequestException as e:
        return JsonResponse({
            'error': f'Ошибка подключения к СКУД: {str(e)}',
            'code': 503
        }, status=503)
    except Exception as e:
        return JsonResponse({
            'error': f'Внутренняя ошибка: {str(e)}',
            'code': 500
        }, status=500)


@csrf_exempt
def download_backup(request):
    """
    Скачать полный бэкап как файл (аналог твоего скрипта)
    Доступно по: https://scud.smit.4gain.pro/api/download_backup
    """
    try:
        from django.utils import timezone
        import datetime

        base_url = settings.SKUD_CONFIG.get('BASE_URL', 'http://188.92.110.218')
        session_cookie = settings.SKUD_CONFIG.get('SESSION_COOKIE')

        if not session_cookie:
            return HttpResponse('Сессионная кука не настроена', status=500)

        # Делаем запрос за всеми данными
        url = f"{base_url}/iclock/api/transactions/"
        params = {
            'format': 'json',
            'page_size': 30000,
            'ordering': '-id',
        }

        cookies = {
            'sessionid': session_cookie
        }

        response = requests.get(url, params=params, cookies=cookies, timeout=60)
        response.raise_for_status()

        data = response.json()

        # Создаем имя файла
        filename = f"skud_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # Возвращаем как файл для скачивания
        http_response = HttpResponse(
            json.dumps(data, ensure_ascii=False, indent=2),
            content_type='application/json'
        )
        http_response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return http_response

    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'code': 500
        }, status=500)