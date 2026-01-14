import requests
import random
import re



class AutoLogger:
    """ класс автоматически получающий куку и CSRF токен"""

    def __init__(self):
        pass

    def get_random_employee(self):
        """ метод для получения случайного сотрудника"""

        employee_pool = ['110', '111', '112', '301', '302', '303',
                         '200', '201', '202', '203', '323', '275',
                         '398', '407', '409', '136', '143', '197',
                         '156', '120', '225', '317', '333', '95',
                         '21', '70', '221', '223', '240', '277']
        random_employee = random.choice(employee_pool)

        return random_employee





