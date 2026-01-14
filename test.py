import requests
import re

session = requests.Session()

session.get('http://188.92.110.218/')

login_url = 'http://188.92.110.218/login/?next=/'

headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Host': '188.92.110.218',
    'Pragma': 'no-cache',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
}

response = session.get(login_url, headers=headers)

csrf_tokens = re.findall(r'csrfmiddlewaretoken["\']?\s*value=["\']([^"\']+)["\']', response.text)
if csrf_tokens:
    csrf_token = csrf_tokens[0]
else:
    exit()

login_data = {
    'csrfmiddlewaretoken': csrf_token,
    'username': '312',
    'password': '123456',
    'login_user': 'employee',
}

headers.update({
    'Content-Type': 'application/x-www-form-urlencoded',
    'Referer': login_url,
    'Origin': 'http://188.92.110.218',
})

response = session.post(login_url, data=login_data, headers=headers)


if response.status_code == 200:

    cookies = session.cookies.get_dict()

    # Ищем сессионные куки
    session_cookies = []
    for name, value in cookies.items():
        print(f"  {name}: {value[:30]}...")
        if 'session' in name.lower():
            session_cookies.append((name, value))

    if session_cookies:
        print(f"\n✓ Найдены сессионные куки: {len(session_cookies)} шт.")
        for name, value in session_cookies:
            print(f"  {name}: {value}")
    else:
        print("\n⚠ Сессионные куки не найдены")

    content_lower = response.text.lower()
    if 'logout' in content_lower or 'выход' in content_lower:
        print("✓ В HTML есть кнопка выхода - авторизация успешна!")
    elif 'логин' in content_lower or 'login' in content_lower:
        print("⚠ В HTML все еще есть форма логина")

    # Сохраняем результат
    with open('result.html', 'w', encoding='utf-8') as f:
        f.write(response.text)
    print("Результат сохранен в result.html")