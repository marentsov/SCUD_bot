import requests
import time

# Конфигурация
URL = "http://188.92.110.218/iclock/api/transactions/?format=json&ordering=-id&page_size=10"
COOKIES = {"sessionid": "qq471oqoqg92zxvnxazickyiejh10xuf"}

# Последний известный ID
last_id = 0

print("Монитор СКУД запущен...")
print("Ожидание новых записей...")

while True:
    try:
        # Получаем данные с таймаутом
        r = requests.get(URL, cookies=COOKIES, timeout=15)
        data = r.json()

        # Проверяем новые записи
        for record in data["data"]:
            record_id = record["id"]

            # Если нашли новую запись
            if record_id > last_id:
                last_id = record_id

                # Выводим информацию
                print(f"\n[НОВЫЙ ПРОХОД] ID: {record_id}")
                print(f"Сотрудник: {record['emp_code']}")
                print(f"Терминал: {record['terminal_alias']}")
                print(f"Время: {record['punch_time']}")
                print(f"Тип: {'ВХОД' if record['punch_state'] == '0' else 'ВЫХОД'}")
                print("-" * 40)

        # Короткая пауза между проверками
        time.sleep(5)

    except requests.exceptions.Timeout:
        print("[Таймаут] Жду 10 секунд...")
        time.sleep(10)
        continue

    except requests.exceptions.ConnectionError:
        print("[Ошибка соединения] Жду 15 секунд...")
        time.sleep(15)
        continue

    except Exception as e:
        print(f"[Ошибка] {type(e).__name__}: {e}")
        time.sleep(10)