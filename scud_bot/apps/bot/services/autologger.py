import requests
import random
import re
import logging
from typing import Optional, Tuple


logger = logging.getLogger(__name__)


class AutoLogger:
    """ класс автоматически получающий куку """

    def __init__(self, base_url: str = "http://188.92.110.21"):
        self.base_url = base_url
        self.session = requests.Session()
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


    def get_random_employee(self) -> Tuple[str,str]:
        """ метод для получения данных случайного сотрудника"""

        employee_pool = [
            ('110', '123456'), ('111', '123456'), ('112', '123456'),
            ('301', '123456'), ('302', '123456'), ('303', '123456'),
            ('200', '123456'), ('201', '123456'), ('202', '123456'),
            ('203', '123456'), ('323', '123456'), ('275', '123456'),
            ('398', '123456'), ('407', '123456'), ('409', '123456'),
            ('136', '123456'), ('143', '123456'), ('197', '123456'),
            ('156', '123456'), ('120', '123456'), ('225', '123456'),
            ('317', '123456'), ('333', '123456'), ('95', '123456'),
            ('21', '123456'), ('70', '123456'), ('221', '123456'),
            ('223', '123456'), ('240', '123456'), ('277', '123456')
        ]
        random_employee = random.choice(employee_pool)

        return random_employee


    def get_new_cookie(self) -> Optional[str]:
        """метод для получения сессионной куки"""

        try:
            self.session.get(f'{self.base_url}/')

            login_url = f'{self.base_url}/login/?next=/'

            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'User-Agent': self.user_agent,
            }

            response = self.session.get(login_url, headers=headers)

            csrf_tokens = re.findall(
                r'csrfmiddlewaretoken["\']?\s*value=["\']([^"\']+)["\']',
                response.text
            )

            if not csrf_tokens:
                logger.error("CSRF токен не найден")
                return None

            csrf_token = csrf_tokens[0]

            username, password = self.get_random_employee()

            # данные для авторизации

            login_data = {
                'csrfmiddlewaretoken': csrf_token,
                'username': username,
                'password': password,
                'login_user': 'employee',
            }

            headers.update({
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': login_url,
                'Origin': self.base_url,
            })

            response = self.session.post(login_url, data=login_data, headers=headers)

            if response.status_code == 200:
                cookies = self.session.cookies.get_dict()

                for name, value in cookies.items():
                    if 'session' in name.lower():
                        logger.info(f"Получена новая кука для пользователя {username}")
                        return value

            logger.error(f'Ошибка при авторизации {response.status_code}')
            return None

        except Exception as e:
            logger.error(f'Ошибка при попытке получения куки - {e}')
            return None







