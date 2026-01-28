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
    """ Скачать полный бэкап как файл с фильтрацией по датам на нашей стороне """
    try:
        base_url = settings.SKUD_CONFIG['BASE_URL']
        session_cookie = settings.SKUD_CONFIG['SESSION_COOKIE']

        if not session_cookie:
            return HttpResponse('Кука не настроена', status=500)

        url = f"{base_url}/iclock/api/transactions/"
        params = {
            'format': 'json',
            'page_size': 80000,
            'ordering': '-id',
        }

        response = _fetch_scud_data(url, params, session_cookie, max_retries=3)
        data = response.json()

        # Получаем все транзакции
        all_transactions = data.get('data', [])

        # Получаем параметры фильтрации
        date_gte = request.GET.get('date__gte')
        date_lte = request.GET.get('date__lte')

        # Если есть параметры фильтрации - фильтруем
        if date_gte or date_lte:
            from datetime import datetime

            # Преобразуем строки дат в datetime объекты для сравнения
            start_date = None
            end_date = None

            if date_gte:
                try:
                    start_date = datetime.strptime(date_gte, '%Y-%m-%d')
                except ValueError:
                    logger.warning(f"Неверный формат даты date__gte: {date_gte}")
                    return HttpResponse('Неверный формат даты date__gte. Используйте YYYY-MM-DD', status=400)

            if date_lte:
                try:
                    end_date = datetime.strptime(date_lte, '%Y-%m-%d')
                except ValueError:
                    logger.warning(f"Неверный формат даты date__lte: {date_lte}")
                    return HttpResponse('Неверный формат даты date__lte. Используйте YYYY-MM-DD', status=400)

            # Фильтруем транзакции
            filtered_transactions = []

            for transaction in all_transactions:
                punch_time_str = transaction.get('punch_time', '')

                if not punch_time_str:
                    continue  # Пропускаем если нет времени

                try:
                    # Парсим дату из транзакции (формат: "2025-12-01 08:30:15")
                    transaction_date = datetime.strptime(punch_time_str[:10], '%Y-%m-%d')

                    include = True

                    # Проверяем фильтры
                    if start_date and transaction_date < start_date:
                        include = False

                    if end_date and transaction_date > end_date:
                        include = False

                    if include:
                        filtered_transactions.append(transaction)

                except ValueError as e:
                    logger.warning(f"Ошибка парсинга даты транзакции: {punch_time_str} - {e}")
                    continue

            # Заменяем данные на отфильтрованные
            data['data'] = filtered_transactions
            data['count'] = len(filtered_transactions)

        # Формируем имя файла с учетом фильтров
        if date_gte and date_lte:
            # Убираем дефисы для имени файла
            date_gte_clean = date_gte.replace('-', '')
            date_lte_clean = date_lte.replace('-', '')
            filename = f"skud_backup_{date_gte_clean}_{date_lte_clean}.json"
        elif date_gte:
            date_gte_clean = date_gte.replace('-', '')
            filename = f"skud_backup_from_{date_gte_clean}.json"
        elif date_lte:
            date_lte_clean = date_lte.replace('-', '')
            filename = f"skud_backup_to_{date_lte_clean}.json"
        else:
            # Если фильтров нет - используем текущую дату
            from datetime import datetime
            filename = f"skud_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # Добавляем информацию о фильтрации в ответ
        if date_gte or date_lte:
            data['filter_info'] = {
                'date_gte': date_gte,
                'date_lte': date_lte,
                'original_count': len(all_transactions),
                'filtered_count': len(data.get('data', [])),
                'filter_applied': True
            }

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