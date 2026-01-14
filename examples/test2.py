import requests


COOKIE = '8egwro05wfki82hp58ah81uf00p6lue1'
URL = 'http://188.92.110.218/iclock/api/transactions/?format=json&ordering=-id&page_size=5'

# Заголовки
headers = {'Cookie': f'sessionid={COOKIE}'}

# Запрос
try:
    r = requests.get(URL, headers=headers, timeout=10)
    print(f'Статус: {r.status_code}')

    if r.status_code == 200:
        data = r.json()
        print(f'✅ Успех! Записей: {len(data.get("data", []))}')
    elif r.status_code == 401:
        print('❌ 401 - Кука не работает')
        print(f'Ответ: {r.text[:100]}')
    else:
        print(f'Код {r.status_code}: {r.text[:100]}')

except Exception as e:
    print(f'Ошибка: {e}')