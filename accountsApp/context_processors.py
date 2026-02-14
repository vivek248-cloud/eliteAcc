from .models import Company
from decimal import Decimal
from django.db.models import Sum
from django.utils.timezone import now
from datetime import timedelta




def selected_company(request):
    company_id = request.session.get('selected_company_id')
    company = Company.objects.filter(id=company_id).first() if company_id else None
    return {
        'selected_company': company,
        'companies': Company.objects.all()
    }



# def smart_alerts(request):

#     if not request.user.is_authenticated:
#         return {}

#     selected_company_id = request.session.get('selected_company_id')
#     if not selected_company_id:
#         return {}

#     from .models import Client, Bank, Payment, Expense

#     payment_qs = Payment.objects.filter(
#         client__company_id=selected_company_id
#     )

#     expense_qs = Expense.objects.filter(
#         client__company_id=selected_company_id
#     )

#     clients = Client.objects.filter(
#         company_id=selected_company_id
#     ).annotate(
#         spent_total=Sum('expenses__amount')
#     )

#     high_budget_clients = 0
#     for c in clients:
#         spent = c.spent_total or Decimal('0')
#         if spent > (c.budget * Decimal('0.8')):
#             high_budget_clients += 1

#     banks = Bank.objects.filter(company_id=selected_company_id)

#     negative_bank_count = 0
#     for bank in banks:
#         payment_total = bank.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
#         expense_total = bank.expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')

#         available = bank.opening_balance + payment_total - expense_total
#         if available < 0:
#             negative_bank_count += 1

#     large_payments_today = payment_qs.filter(
#         payment_date=now().date(),
#         amount__gt=Decimal('100000')
#     ).count()

#     alert_count = high_budget_clients + negative_bank_count + large_payments_today

#     return {
#         'alert_count': alert_count,
#         'high_budget_clients': high_budget_clients,
#         'negative_bank_count': negative_bank_count,
#         'large_payments_today': large_payments_today,
#     }






from django.db.models import Avg, Sum
from django.utils.timezone import now
from datetime import timedelta
from decimal import Decimal
from .models import Payment, Expense, Bank


def global_alerts(request):

    if not request.user.is_authenticated:
        return {}

    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return {}

    today = now().date()
    thirty_days_ago = today - timedelta(days=30)

    # ---------------------------------
    # Base Querysets
    # ---------------------------------
    payment_qs = Payment.objects.filter(
        client__company_id=selected_company_id
    )

    expense_qs = Expense.objects.filter(
        client__company_id=selected_company_id
    )

    # ---------------------------------
    # 💰 PAYMENT ALERT (30-day avg)
    # ---------------------------------
    last_30_payments = payment_qs.filter(
        payment_date__gte=thirty_days_ago,
        payment_date__lt=today
    )

    avg_payment_30 = last_30_payments.aggregate(
        avg=Avg('amount')
    )['avg'] or Decimal('0')

    large_payment_count = payment_qs.filter(
        payment_date=today,
        amount__gt=avg_payment_30
    ).count()

    # ---------------------------------
    # ⚠ EXPENSE ALERT (30-day avg)
    # ---------------------------------
    last_30_expenses = expense_qs.filter(
        expense_date__gte=thirty_days_ago,
        expense_date__lt=today
    )

    avg_expense_30 = last_30_expenses.aggregate(
        avg=Avg('amount')
    )['avg'] or Decimal('0')

    high_expense_count = expense_qs.filter(
        expense_date=today,
        amount__gt=avg_expense_30
    ).count()

    # ---------------------------------
    # 🔴 TRUE NEGATIVE BANK ALERT
    # ---------------------------------
    banks = Bank.objects.filter(company_id=selected_company_id)

    negative_bank_count = 0

    for bank in banks:
        payment_total = bank.payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        expense_total = bank.expenses.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        available_balance = (
            bank.opening_balance +
            payment_total -
            expense_total
        )

        if available_balance < 0:
            negative_bank_count += 1

    # ---------------------------------
    # 🚨 Final Alert Count
    # ---------------------------------
    alert_count = (
        large_payment_count +
        high_expense_count +
        negative_bank_count
    )

    alerts_seen = request.session.get('alerts_seen', False)

    return {
        'alert_count': 0 if alerts_seen else alert_count,
        'large_payment_count': large_payment_count,
        'high_expense_count': high_expense_count,
        'negative_bank_count': negative_bank_count,
        'avg_payment': avg_payment_30,
        'avg_expense': avg_expense_30,
    }
