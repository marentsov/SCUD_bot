from django.core.management.base import BaseCommand
from ...models import Employee, Transaction


class Command(BaseCommand):
    help = 'Проверить и привязать транзакции для всех сотрудников'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Автоматически привязать непривязанные записи'
        )
        parser.add_argument(
            '--emp-code',
            type=str,
            help='Проверить только конкретного сотрудника'
        )

    def handle(self, *args, **options):
        fix = options['fix']
        emp_code = options.get('emp_code')

        if emp_code:
            employees = Employee.objects.filter(emp_code=emp_code)
        else:
            employees = Employee.objects.all()

        total_unlinked = 0
        total_linked = 0

        self.stdout.write("Проверка привязки транзакций сотрудников")

        for employee in employees:
            unlinked = Transaction.objects.filter(
                emp_code=employee.emp_code,
                employee__isnull=True
            ).count()

            total_unlinked += unlinked

            if unlinked > 0:
                self.stdout.write(
                    f"{employee.name} ({employee.emp_code}): "
                    f"{unlinked} непривязанных записей"
                )

                if fix:
                    Transaction.objects.filter(
                        emp_code=employee.emp_code,
                        employee__isnull=True
                    ).update(employee=employee)

                    self.stdout.write(f"Привязано {unlinked} записей")
                    total_linked += unlinked
            else:
                self.stdout.write(
                    f"{employee.name} ({employee.emp_code}): "
                    "все записи привязаны"
                )

        self.stdout.write(f"ИТОГО:")
        self.stdout.write(f"Сотрудников проверено: {employees.count()}")
        self.stdout.write(f"Непривязанных записей: {total_unlinked}")

        if fix:
            self.stdout.write(f"Привязано записей: {total_linked}")
        elif total_unlinked > 0:
            self.stdout.write("\nДля привязки запустите с ключом --fix")
            self.stdout.write("Или: python manage.py check_and_link_all --fix")