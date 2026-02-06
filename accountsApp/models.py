from django.db import models
from django.db.models import Sum
from django.db import models
from django.db.models import Sum
from decimal import Decimal
from django.utils import timezone

# Company Model

class Company(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


# client Model



from decimal import Decimal
from django.db import models
from django.db.models import Sum

class Client(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='clients'
    )
    name = models.CharField(max_length=255)
    budget = models.DecimalField(max_digits=12, decimal_places=2)

    # 💳 TOTAL PAID (CASH + CHEQUE)
    def total_paid(self):
        return self.payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

    # 🔴 TOTAL SPENT
    def total_expenses(self):
        return self.expenses.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

    # 💰 BALANCE = PAID − SPENT
    def balance(self):
        return self.total_paid() - self.total_expenses()

    def yet_to_pay(self):
        return self.budget - self.total_paid()

    def __str__(self):
        return self.name







#bank Model


class Bank(models.Model):
    name = models.CharField(max_length=255, unique=True)

    opening_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    available_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    def calculated_balance(self):
        payments = self.payments.aggregate(
            total=Sum('amount')
        )['total'] or 0

        expenses = self.expenses.aggregate(
            total=Sum('amount')
        )['total'] or 0

        return self.opening_balance + payments - expenses

    def recalculate_balance(self, save=True):
        self.available_balance = self.calculated_balance()
        if save:
            self.save(update_fields=['available_balance'])
        return self.available_balance

    def __str__(self):
        return self.name




#cash Model

class Cash(models.Model):
    CASH_IN = 'in'
    CASH_OUT = 'out'

    CASH_TYPE_CHOICES = [
        (CASH_IN, 'Cash In'),
        (CASH_OUT, 'Cash Out'),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='cash_transactions'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    cash_type = models.CharField(max_length=10, choices=CASH_TYPE_CHOICES)
    description = models.CharField(max_length=255, blank=True)
    cash_date = models.DateField(default=timezone.now)

    def __str__(self):
        return f"{self.get_cash_type_display()} ₹{self.amount}"








# payment Model

class Payment(models.Model):
    CASH = 'cash'
    CHEQUE = 'cheque'

    PAYMENT_MODE_CHOICES = [
        (CASH, 'Cash'),
        (CHEQUE, 'Cheque'),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    bank = models.ForeignKey(
        Bank,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_MODE_CHOICES)
    payment_date = models.DateField()

    def __str__(self):
        return f"{self.client.name} - ₹{self.amount}"



# worker Model
class Worker(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# expense category Model

class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    



# expense Model

class Expense(models.Model):
    CASH = 'cash'
    CHEQUE = 'cheque'

    SPEND_MODE_CHOICES = [
        (CASH, 'Cash'),
        (CHEQUE, 'Cheque'),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='expenses'
    )

    bank = models.ForeignKey(
        Bank,
        on_delete=models.CASCADE,
        related_name='expenses'
    )

    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # 🆕 SALARY TO (WORKER)
    salary_to = models.ForeignKey(
        Worker,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='salary_expenses'
    )
    
    description = models.TextField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    spend_mode = models.CharField(max_length=10, choices=SPEND_MODE_CHOICES)
    expense_date = models.DateField()

    def __str__(self):
        return f"{self.client.name} - ₹{self.amount}"





class AppSettings(models.Model):
    notification_email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.notification_email or "No email set"
