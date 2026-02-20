from urllib import request
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from .models import *
from decimal import Decimal
from django.contrib import messages
import json
from decimal import Decimal
from django.contrib.auth.decorators import login_required

from django.db.models.functions import TruncDate
from django.utils.dateparse import parse_date

from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def login_view(request):

    # Already logged in
    if request.user.is_authenticated:
        return redirect('dashboard')

    # Show session expired message
    if request.session.pop('session_expired', False):
        messages.warning(request, "⏳ Your session expired. Please login again.")

    if request.method == 'POST':

        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user and user.is_staff:
            login(request, user)

            # 🔐 Get last page safely
            redirect_to = request.session.pop('last_page', None)

            # Prevent redirect to login/logout
            blocked_paths = [
                reverse('login'),
                reverse('logout'),
            ]

            if (
                redirect_to
                and url_has_allowed_host_and_scheme(
                    redirect_to,
                    allowed_hosts={request.get_host()}
                )
                and not any(redirect_to.startswith(p) for p in blocked_paths)
            ):
                return redirect(redirect_to)

            return redirect('dashboard')

        messages.error(request, "Invalid credentials")

    return render(request, 'auth/login.html')







from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_view(request):
    logout(request)
    request.session.flush()  # optional but cleaner
    return redirect('login')







from django.urls import reverse


from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect

def switch_company(request, pk):

    company = get_object_or_404(Company, pk=pk)

    # ✅ Save selected company
    request.session['selected_company_id'] = company.id

    # ✅ Get previous page safely
    next_url = request.META.get('HTTP_REFERER')

    if not next_url:
        return redirect('dashboard')

    blocked_paths = [
        reverse('login'),
        reverse('logout'),
    ]

    if any(next_url.startswith(p) for p in blocked_paths):
        return redirect('dashboard')

    return HttpResponseRedirect(next_url)




from django.utils.timezone import now
from django.db.models.functions import TruncMonth
from django.db.models import Avg


@login_required(login_url='login')
def home(request):

    companies = Company.objects.all().order_by('name')



    selected_company_id = request.session.get('selected_company_id')
    selected_company = Company.objects.filter(
        id=selected_company_id
    ).first()

    selected_bank_id = request.GET.get('bank')

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    sd = parse_date(start_date) if start_date else None
    ed = parse_date(end_date) if end_date else None

    if not selected_company_id:
        return render(request, 'dashboard.html', {
            'companies': companies,
            'selected_company_id': None,
        })

    # =========================
    # BASE QUERYSETS
    # =========================
    payment_qs = Payment.objects.filter(
        client__company_id=selected_company_id
    )

    expense_qs = Expense.objects.filter(
        client__company_id=selected_company_id
    )

    if sd:
        payment_qs = payment_qs.filter(payment_date__gte=sd)
        expense_qs = expense_qs.filter(expense_date__gte=sd)

    if ed:
        payment_qs = payment_qs.filter(payment_date__lte=ed)
        expense_qs = expense_qs.filter(expense_date__lte=ed)

    # =========================
    # TOTAL PAYMENTS & EXPENSES
    # =========================
    totals = payment_qs.aggregate(
        total_payments=Sum('amount')
    )

    total_payments = totals['total_payments'] or Decimal('0.00')

    total_expenses = expense_qs.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    # =========================
    # RECEIVABLES (NO LOOP)
    # =========================
    clients = Client.objects.filter(
        company_id=selected_company_id
    ).annotate(
        paid_total=Sum('payments__amount')
    )

    total_balance = Decimal('0.00')

    for c in clients:
        paid = c.paid_total or Decimal('0.00')
        total_balance += (c.budget - paid)

    # =========================
    # EXTRA DATA FOR HEALTH SYSTEM
    # =========================
    total_project_value = Decimal('0.00')
    overrun_clients = 0
    high_budget_clients = 0

    for c in clients:
        paid = c.paid_total or Decimal('0.00')
        spent = c.expenses.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        total_project_value += c.budget

        if spent > c.budget:
            overrun_clients += 1

        if spent > (c.budget * Decimal('0.8')):
            high_budget_clients += 1

    total_clients = clients.count()


    # =========================
    # BANKS (COMPANY SAFE)
    # =========================
    banks = Bank.objects.filter(
        company_id=selected_company_id
    )

    for bank in banks:

        payment_total = bank.payments.filter(
            client__company_id=selected_company_id
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        expense_total = bank.expenses.filter(
            client__company_id=selected_company_id
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        bank.available_balance = (
            bank.opening_balance + payment_total - expense_total
        )

    total_bank = sum((b.available_balance for b in banks), Decimal('0.00'))

    negative_bank_count = sum(
    1 for b in banks if b.available_balance < 0
)


    # Selected bank
    selected_bank = None
    if selected_bank_id:
        selected_bank = banks.filter(id=selected_bank_id).first()
        display_bank_balance = (
            selected_bank.available_balance if selected_bank else Decimal('0.00')
        )
    else:
        display_bank_balance = total_bank



    # =========================
    # PROFIT
    # =========================
    total_profit = total_payments - total_expenses
    profit_percentage = (
        (total_profit / total_payments) * 100
        if total_payments > 0 else 0
    )




    # ====================================
    # 💎 FINANCIAL HEALTH SCORE (0-100)
    # ====================================

    # 1️⃣ Profit Score (25 max)
    if profit_percentage > 30:
        profit_score = 25
    elif profit_percentage > 15:
        profit_score = 18
    elif profit_percentage > 5:
        profit_score = 10
    elif profit_percentage > 0:
        profit_score = 5
    else:
        profit_score = 0

    # 2️⃣ Cash Ratio Score
    cash_ratio = (
        total_bank / total_expenses
        if total_expenses > 0 else Decimal('0')
    )

    if cash_ratio > 2:
        cash_score = 25
    elif cash_ratio > 1:
        cash_score = 18
    elif cash_ratio > 0.5:
        cash_score = 10
    else:
        cash_score = 5

    # 3️⃣ Receivable Ratio Score
    receivable_ratio = (
        total_balance / total_project_value
        if total_project_value > 0 else Decimal('0')
    )

    if receivable_ratio < Decimal('0.2'):
        receivable_score = 25
    elif receivable_ratio < Decimal('0.4'):
        receivable_score = 18
    elif receivable_ratio < Decimal('0.6'):
        receivable_score = 10
    else:
        receivable_score = 5

    # 4️⃣ Budget Discipline Score
    discipline_ratio = (
        Decimal(overrun_clients) / Decimal(total_clients)
        if total_clients > 0 else Decimal('0')
    )

    if discipline_ratio == 0:
        discipline_score = 25
    elif discipline_ratio < Decimal('0.1'):
        discipline_score = 18
    elif discipline_ratio < Decimal('0.3'):
        discipline_score = 10
    else:
        discipline_score = 5

    health_score = (
        profit_score +
        cash_score +
        receivable_score +
        discipline_score
    )

    if health_score >= 75:
        health_status = "Stable"
    elif health_score >= 50:
        health_status = "Moderate Risk"
    else:
        health_status = "High Risk"







    # ====================================
    # 📊 TOP 5 EXPENSE CATEGORIES
    # ====================================
    top_categories = (
        expense_qs
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')[:5]
    )

    top_category_labels = [
        c['category__name'] or "Uncategorized"
        for c in top_categories
    ]

    top_category_values = [
        float(c['total']) for c in top_categories
    ]



    # ====================================
    # 👷 SALARY DISTRIBUTION BY TEAM
    # ====================================
    salary_qs = expense_qs.filter(category__name__iexact='salary')

    salary_by_team = (
        salary_qs
        .values('salary_to__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    salary_team_labels = [
        s['salary_to__name'] or "Unknown"
        for s in salary_by_team
    ]

    salary_team_values = [
        float(s['total']) for s in salary_by_team
    ]



    # ====================================
    # 📉 MONTHLY EXPENSE TREND
    # ====================================
    monthly_expenses = (
        expense_qs
        .annotate(month=TruncMonth('expense_date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

    monthly_expense_labels = [
        m['month'].strftime("%b %Y")
        for m in monthly_expenses
    ]

    monthly_expense_values = [
        float(m['total']) for m in monthly_expenses
    ]



    # ====================================
    # 🚨 SMART ALERTS (INTELLIGENT VERSION)
    # ====================================

    today = now().date()

    # ---- Average Payment
    avg_payment = payment_qs.aggregate(
        avg=Avg('amount')
    )['avg'] or Decimal('0.00')

    large_payments_today = payment_qs.filter(
        payment_date=today,
        amount__gt=avg_payment
    )

    large_payment_count = large_payments_today.count()

    # ---- Average Expense
    avg_expense = expense_qs.aggregate(
        avg=Avg('amount')
    )['avg'] or Decimal('0.00')

    high_expense_today = expense_qs.filter(
        expense_date=today,
        amount__gt=avg_expense
    )

    high_expense_count = high_expense_today.count()

    # ---- Negative Bank Alert (already calculated earlier)
    # negative_bank_count

    # ---- Final Alert Count
    alert_count = (
        large_payment_count +
        high_expense_count +
        negative_bank_count
    )



    # =========================
    # RECENT DATA
    # =========================
    recent_payments = payment_qs.select_related(
        'client', 'bank'
    ).order_by('-payment_date')[:5]

    recent_expenses = expense_qs.select_related(
        'client', 'category'
    ).order_by('-expense_date')[:5]

    # =========================
    # RECENT CYCLE TOTAL
    # =========================
    recent_total = recent_payments.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    # =========================
    # CURRENT MONTH RECEIVED
    # =========================
    today = now()

    monthly_received_total = payment_qs.filter(
        payment_date__year=today.year,
        payment_date__month=today.month
    ).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    # =========================
    # GRAPH DATA
    # =========================
    payment_chart = (
        payment_qs
        .annotate(day=TruncDate('payment_date'))
        .values('day')
        .annotate(total=Sum('amount'))
        .order_by('day')
    )

    expense_chart = (
        expense_qs
        .annotate(day=TruncDate('expense_date'))
        .values('day')
        .annotate(total=Sum('amount'))
        .order_by('day')
    )

    payment_labels = [str(p['day']) for p in payment_chart]
    payment_values = [float(p['total']) for p in payment_chart]

    expense_labels = [str(e['day']) for e in expense_chart]
    expense_values = [float(e['total']) for e in expense_chart]

    all_dates = sorted(set(payment_labels + expense_labels))
    profit_trend_data = []

    for d in all_dates:
        p = payment_values[payment_labels.index(d)] if d in payment_labels else 0
        e = expense_values[expense_labels.index(d)] if d in expense_labels else 0
        profit_trend_data.append(p - e)
    current_date = now()


    return render(request, 'dashboard.html', {
        'companies': companies,
        'selected_company_id': selected_company_id,

        'clients': clients,
        'banks': banks,

        'total_bank': total_bank,
        'display_bank_balance': display_bank_balance,
        'selected_bank': selected_bank,
        'selected_bank_id': selected_bank_id,

        'total_balance': total_balance,
        'total_payments': total_payments,
        'total_expenses': total_expenses,

        'recent_payments': recent_payments,
        'recent_expenses': recent_expenses,

        'start_date': start_date,
        'end_date': end_date,

        'total_profit': total_profit,
        'profit_percentage': profit_percentage,
        'recent_total': recent_total,
        'monthly_received_total': monthly_received_total,
        'current_date': current_date,




        'health_score': health_score,
        'health_status': health_status,
        'expense_category_labels': json.dumps(top_category_labels),
        'expense_category_values': json.dumps(top_category_values),

        'salary_team_labels': json.dumps(salary_team_labels),
        'salary_team_values': json.dumps(salary_team_values),

        'monthly_expense_labels': json.dumps(monthly_expense_labels),
        'monthly_expense_values': json.dumps(monthly_expense_values),
        'alert_count': alert_count,

        'large_payment_count': large_payment_count,
        'high_expense_count': high_expense_count,
        'avg_payment': avg_payment,
        'avg_expense': avg_expense,
        'negative_bank_count': negative_bank_count,




        'profit_trend_labels': json.dumps(all_dates),
        'profit_trend_values': json.dumps(profit_trend_data),

        'payment_labels': json.dumps(payment_labels),
        'payment_values': json.dumps(payment_values),
        'expense_labels': json.dumps(expense_labels),
        'expense_values': json.dumps(expense_values),
    })


#clear alert when user visited

from django.http import JsonResponse

@login_required
def clear_alerts(request):
    request.session['alerts_seen'] = True
    return JsonResponse({"status": "ok"})



# accountsApp/views.py

from datetime import timedelta



def fill_date_gaps(qs):
    """
    qs: queryset with keys ['day', 'total']
    Returns: labels[], values[] with missing dates filled
    """

    data_map = {
        row['day']: float(row['total']) for row in qs
    }

    if not data_map:
        return [], []

    start_date = min(data_map.keys())
    end_date = max(data_map.keys())

    labels = []
    values = []

    current = start_date
    while current <= end_date:
        labels.append(current.strftime('%d-%m-%Y'))
        values.append(data_map.get(current, 0.0))
        current += timedelta(days=1)

    return labels, values





#index view for Company


from django.db.models import Count



def company_index(request):
    companies = Company.objects.annotate(
        total_clients=Count('clients', distinct=True),
        total_banks=Count('banks', distinct=True),
        total_worker_teams=Count('workers', distinct=True),
        total_workers=Count('workers__names', distinct=True),  # ✅ FIXED
    ).order_by('-id')

    return render(request, 'company/index.html', {
        'companies': companies
    })


#create view for Company

def company_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        logo = request.FILES.get('logo')

        if name:
            Company.objects.create(
                name=name,
                logo=logo
            )
            messages.success(request, "Company created successfully")
            return redirect('company_index')

        messages.error(request, "Company name is required")

    return render(request, 'company/create.html')

def company_delete(request, pk):
    company = get_object_or_404(Company, pk=pk)

    if request.method == 'POST':
        company.delete()
        return redirect('company_index')

    return render(request, 'company/delete.html', {
        'company': company
    })


#update view for Company

def company_update(request, pk):
    company = get_object_or_404(Company, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name')
        logo = request.FILES.get('logo')

        if name:
            company.name = name

            # Only update logo if new file uploaded
            if logo:
                company.logo = logo

            company.save()
            messages.success(request, "Company updated successfully")
            return redirect('company_index')

        messages.error(request, "Company name is required")

    return render(request, 'company/update.html', {
        'company': company
    })



#client views will be added here

from django.db.models import Sum, Q
from decimal import Decimal
from django.contrib.auth.decorators import login_required


@login_required(login_url='login')
def client_index(request):

    selected_company_id = request.session.get('selected_company_id')

    if not selected_company_id:
        return render(request, 'client/index.html', {
            'clients': [],
            'expense_type': request.GET.get('expense_type', 'all'),
        })

    expense_type = request.GET.get('expense_type', 'all')

    clients = Client.objects.filter(
        company_id=selected_company_id
    ).select_related('company')

    client_data = []

    # =========================
    # BUILD CLIENT DATA FIRST
    # =========================
    for client in clients:

        payments_total = client.payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        expenses_qs = client.expenses.select_related('category')

        if expense_type == 'business':
            expenses_qs = expenses_qs.exclude(
                Q(category__name__iexact='home') |
                Q(category__name__iexact='personal')
            )

        elif expense_type == 'personal':
            expenses_qs = expenses_qs.filter(
                Q(category__name__iexact='home') |
                Q(category__name__iexact='personal')
            )

        expenses_total = expenses_qs.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        balance = payments_total - expenses_total
        yet_to_pay = client.budget - payments_total

        client_data.append({
            'id': client.id,
            'name': client.name,
            'location': client.location,
            'company': client.company,
            'budget': client.budget,
            'total_paid': payments_total,
            'total_expenses': expenses_total,
            'balance': balance,
            'yet_to_pay': yet_to_pay,
        })

    # =========================
    # CALCULATE TOTALS AFTER LOOP
    # =========================
    total_project_budget = sum(c['budget'] for c in client_data)
    total_paid = sum(c['total_paid'] for c in client_data)
    total_spend = sum(c['total_expenses'] for c in client_data)

    total_balance = total_paid - total_spend
    total_yet_to_receive = total_project_budget - total_paid

    return render(request, 'client/index.html', {
        'clients': client_data,
        'expense_type': expense_type,
        'total_project_budget': total_project_budget,
        'total_paid': total_paid,
        'total_spend': total_spend,
        'total_balance': total_balance,
        'total_yet_to_receive': total_yet_to_receive,
    })








from decimal import Decimal, InvalidOperation
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from .models import Client, Company


@login_required(login_url='login')
def client_create(request):

    # 🏢 COMPANY FROM SESSION
    selected_company_id = request.session.get('selected_company_id')

    if not selected_company_id:
        messages.error(request, "Please select a company first.")
        return redirect('dashboard')

    company = Company.objects.filter(id=selected_company_id).first()

    if not company:
        messages.error(request, "Company not found.")
        return redirect('dashboard')

    if request.method == 'POST':
        name = request.POST.get('name')
        location = request.POST.get('location')  # ✅ now used
        budget = request.POST.get('budget')

        if not name or not budget:
            messages.error(request, "Name and budget are required.")
            return redirect('client_create')

        try:
            budget_decimal = Decimal(budget)
        except InvalidOperation:
            messages.error(request, "Invalid budget amount.")
            return redirect('client_create')

        # ✅ CREATE CLIENT
        Client.objects.create(
            company=company,
            name=name,
            location=location,  # ✅ IMPORTANT FIX
            budget=budget_decimal
        )

        messages.success(request, "Client created successfully.")
        return redirect('client_index')

    return render(request, 'client/create.html', {
        'company': company,
    })









@login_required(login_url='login')
def client_update(request, pk):

    # 🏢 COMPANY FROM SESSION
    selected_company_id = request.session.get('selected_company_id')

    if not selected_company_id:
        return redirect('dashboard')

    company = get_object_or_404(Company, id=selected_company_id)

    # 🔒 Fetch client ONLY from selected company
    client = get_object_or_404(
        Client,
        pk=pk,
        company_id=selected_company_id
    )

    if request.method == 'POST':
        client.name = request.POST.get('name')
        client.budget = Decimal(request.POST.get('budget'))
        client.location = request.POST.get('location')
        client.save()

        return redirect('client_index')

    return render(request, 'client/update.html', {
        'client': client,
        'company': company,
    })




def client_delete(request, pk):
    client = get_object_or_404(Client, pk=pk)

    if request.method == 'POST':
        client.delete()
        return redirect('client_index')

    return render(request, 'client/delete.html', {
        'client': client
    })



from django.utils.dateparse import parse_date

from decimal import Decimal


from decimal import Decimal
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.dateparse import parse_date


def client_info(request, pk):

    # =========================
    # 🏢 COMPANY SESSION CHECK
    # =========================
    selected_company_id = request.session.get('selected_company_id')

    if not selected_company_id:
        return redirect('dashboard')

    # 🔐 Client must belong to selected company
    client = get_object_or_404(
        Client,
        pk=pk,
        company_id=selected_company_id
    )

    payments_qs = client.payments.select_related('bank')

    expenses_qs = client.expenses.select_related(
        'bank',
        'category',
        'subcategory',
        'salary_to',
        'worker_name'
    )

    # =========================
    # 🔍 FILTER VALUES
    # =========================
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    spend_mode = request.GET.get('spend_mode')
    category_id = request.GET.get('category')
    subcategory_id = request.GET.get('subcategory')
    worker_id = request.GET.get('worker')
    worker_name_id = request.GET.get('worker_name')

    # =========================
    # 📅 DATE FILTERS
    # =========================
    if start_date:
        sd = parse_date(start_date)
        expenses_qs = expenses_qs.filter(expense_date__gte=sd)

    if end_date:
        ed = parse_date(end_date)
        expenses_qs = expenses_qs.filter(expense_date__lte=ed)

    # =========================
    # 💳 SPEND MODE
    # =========================
    if spend_mode:
        expenses_qs = expenses_qs.filter(spend_mode=spend_mode)

    # =========================
    # 🏷 CATEGORY (company safe)
    # =========================
    if category_id:
        expenses_qs = expenses_qs.filter(
            category_id=category_id,
            category__company_id=selected_company_id
        )

    # =========================
    # 🏷 SUBCATEGORY (company safe)
    # =========================
    if subcategory_id:
        expenses_qs = expenses_qs.filter(
            subcategory_id=subcategory_id,
            subcategory__company_id=selected_company_id
        )

    # =========================
    # 👷 WORKER TEAM
    # =========================
    if worker_id:
        expenses_qs = expenses_qs.filter(
            salary_to_id=worker_id,
            salary_to__company_id=selected_company_id
        )

    # =========================
    # 👤 WORKER NAME
    # =========================
    if worker_name_id:
        expenses_qs = expenses_qs.filter(
            worker_name_id=worker_name_id,
            worker_name__worker__company_id=selected_company_id
        )

    # =========================
    # ORDER
    # =========================
    payments_qs = payments_qs.order_by('payment_date', 'id')
    expenses_qs = expenses_qs.order_by('expense_date', 'id')

    # =========================
    # 💰 PAYMENT CUMULATIVE
    # =========================
    running_paid = Decimal('0.00')
    payment_rows = []

    for p in payments_qs:
        before = running_paid
        running_paid += p.amount
        remaining = client.budget - running_paid

        payment_rows.append({
            'date': p.payment_date,
            'amount': p.amount,
            'mode': p.payment_mode,
            'bank': p.bank.name if p.bank else 'Cash',
            'before': before,
            'remaining': remaining,
        })

    # =========================
    # 🔴 EXPENSE CUMULATIVE
    # =========================
    total_paid = running_paid
    running_spent = Decimal('0.00')
    expense_rows = []

    for e in expenses_qs:
        before = running_spent
        running_spent += e.amount
        remaining = total_paid - running_spent

        if e.salary_to:
            team_name = e.salary_to.name
            worker_name = e.worker_name.name if e.worker_name else None
            worker_display = f"{team_name} / {worker_name}" if worker_name else team_name
        else:
            worker_display = None

        expense_rows.append({
            'date': e.expense_date,
            'description': e.description,
            'category': e.category.name if e.category else None,
            'subcategory': e.subcategory.name if e.subcategory else None,
            'before': before,
            'now': e.amount,
            'remaining': remaining,
            'mode': e.spend_mode,
            'bank': e.bank.name if e.bank else 'Cash',
            'worker': worker_display,
        })

    # ✅ Correct totals AFTER loop
    total_spend = running_spent
    net_balance = total_paid - total_spend
    remaining_amount = client.budget - total_paid

    return render(request, 'client/clientinfo.html', {
        'client': client,
        'payments': payment_rows,
        'expenses': expense_rows,

        # filters
        'start_date': start_date,
        'end_date': end_date,
        'spend_mode': spend_mode,
        'total_spend': total_spend,
        'net_balance': net_balance,
        'remaining_amount': remaining_amount,
        'selected_category': category_id,
        'selected_subcategory': subcategory_id,
        'selected_worker': worker_id,
        'selected_worker_name': worker_name_id,

        # dropdown data
        'categories': ExpenseCategory.objects.filter(
            company_id=selected_company_id
        ),

        'subcategories': ExpenseSubCategory.objects.filter(
            company_id=selected_company_id
        ).select_related('category'),

        'workers': Worker.objects.filter(
            company_id=selected_company_id
        ),

        'worker_names': WorkerName.objects.filter(
            worker__company_id=selected_company_id
        ).select_related('worker'),
    })





# export pdf views will be added here



from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from django.http import HttpResponse
from decimal import Decimal
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Sum


def client_info_pdf(request, pk):

    # =========================
    # 🏢 COMPANY SESSION CHECK
    # =========================
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    client = get_object_or_404(
        Client,
        pk=pk,
        company_id=selected_company_id
    )

    payments_qs = client.payments.select_related('bank')
    expenses_qs = client.expenses.select_related(
        'bank', 'salary_to', 'worker_name'
    )

    # =========================
    # 🔍 FILTERS
    # =========================
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    payment_mode = request.GET.get('payment_mode')
    spend_mode = request.GET.get('spend_mode')

    if start_date:
        sd = parse_date(start_date)
        payments_qs = payments_qs.filter(payment_date__gte=sd)
        expenses_qs = expenses_qs.filter(expense_date__gte=sd)

    if end_date:
        ed = parse_date(end_date)
        payments_qs = payments_qs.filter(payment_date__lte=ed)
        expenses_qs = expenses_qs.filter(expense_date__lte=ed)

    if payment_mode:
        payments_qs = payments_qs.filter(payment_mode=payment_mode)

    if spend_mode:
        expenses_qs = expenses_qs.filter(spend_mode=spend_mode)

    payments_qs = payments_qs.order_by('payment_date', 'id')
    expenses_qs = expenses_qs.order_by('expense_date', 'id')

    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        'header_style',
        parent=styles['Title'],
        fontSize=20,
        spaceAfter=10
    )

    # =========================
    # 💰 PAYMENTS
    # =========================
    running_paid = Decimal('0.00')
    payment_rows = []

    for p in payments_qs:
        before = running_paid
        running_paid += p.amount
        remaining = client.budget - running_paid

        payment_rows.append([
            p.payment_date.strftime('%d-%m-%Y'),
            f"Rs. {before:,.2f}",
            f"Rs. {p.amount:,.2f}",
            f"Rs. {remaining:,.2f}",
            p.payment_mode.capitalize(),
            p.bank.name if p.bank else 'Cash'
        ])

    total_paid = running_paid

    # =========================
    # 🔴 EXPENSES
    # =========================
    running_spent = Decimal('0.00')
    expense_rows = []

    for e in expenses_qs:
        before = running_spent
        running_spent += e.amount
        remaining = total_paid - running_spent

        # 👷 Worker Display
        if e.salary_to:
            team = e.salary_to.name
            name = e.worker_name.name if e.worker_name else None
            worker_display = f"{team} / {name}" if name else team
        else:
            worker_display = '—'

        expense_rows.append([
            e.expense_date.strftime('%d-%m-%Y'),
            e.category.name if e.category else '—',
            e.description,
            worker_display,
            f"Rs.{e.amount:,.2f}",
            f"Rs.{remaining:,.2f}",
            e.spend_mode.capitalize(),
            e.bank.name if e.bank else 'Cash'
        ])

    total_spent = running_spent
    final_balance = total_paid - total_spent

    # =========================
    # 📄 PDF SETUP (LANDSCAPE)
    # =========================
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{client.name}_statement.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    elements = []

    # =========================
    # 🧾 HEADER
    # =========================
    elements.append(Paragraph("CLIENT FINANCIAL STATEMENT", header_style))
    elements.append(Spacer(1, 6))
    elements.append(
        Paragraph(f"<b>Client:</b> {client.name}", styles['Normal'])
    )
    elements.append(
        Paragraph(f"<b>Project Value:</b> Rs. {client.budget:,.2f}", styles['Normal'])
    )
    elements.append(Spacer(1, 20))

    # =========================
    # 💰 PAYMENTS TABLE
    # =========================
    elements.append(Paragraph("PAYMENTS", styles['Heading2']))
    elements.append(Spacer(1, 8))

    payment_table = Table(
        [['Date', 'Before', 'Paid', 'Remaining', 'Mode', 'Bank']]
        + payment_rows,
        colWidths=[90, 110, 110, 120, 90, 120]
    )

    payment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E79')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.whitesmoke, colors.transparent]),
    ]))

    elements.append(payment_table)
    elements.append(Spacer(1, 20))

    # =========================
    # 🔴 EXPENSES TABLE
    # =========================
    elements.append(Paragraph("EXPENSES", styles['Heading2']))
    elements.append(Spacer(1, 8))

    expense_table = Table(
        [['Date', 'Category','Description', 'Worker', 'Spent', 'Remaining', 'Mode', 'Bank']]
        + expense_rows,
        colWidths=[70, 100, 140, 110, 95, 110, 70, 90]
    )

    expense_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7A1F1F')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.whitesmoke, colors.transparent]),
    ]))

    elements.append(expense_table)
    elements.append(Spacer(1, 25))

    # =========================
    # 📦 SUMMARY BOX
    # =========================
    summary_table = Table(
        [
            ['TOTAL PAID', f"Rs. {total_paid:,.2f}"],
            ['TOTAL SPENT', f"Rs. {total_spent:,.2f}"],
            ['FINAL BALANCE', f"Rs. {final_balance:,.2f}"],
        ],
        colWidths=[250, 200]
    )

    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F2F2F2')),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))

    elements.append(summary_table)

    doc.build(elements)
    return response









from decimal import Decimal
from django.shortcuts import render
from django.utils.dateparse import parse_date
from django.db.models import Sum
from .models import Client, Payment, Expense


from decimal import Decimal
from itertools import chain
from django.shortcuts import render
from django.utils.dateparse import parse_date
from django.db.models import Sum, F, Value
from django.db.models.functions import Coalesce
from .models import Client, Payment, Expense


from decimal import Decimal
from django.shortcuts import render, redirect
from django.utils.dateparse import parse_date
from django.contrib.auth.decorators import login_required


@login_required(login_url='login')
def all_client_index(request):

    selected_company_id = request.session.get('selected_company_id')

    if not selected_company_id:
        return redirect('dashboard')

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    order = request.GET.get('order', 'new')
    txn_type = request.GET.get('txn_type', 'all')

    sd = parse_date(start_date) if start_date else None
    ed = parse_date(end_date) if end_date else None

    rows = []

    clients = Client.objects.filter(
        company_id=selected_company_id
    ).select_related('company')

    # =========================
    # BUILD ROWS
    # =========================
    for client in clients:

        payments = client.payments.all()
        expenses = client.expenses.all()

        if sd:
            payments = payments.filter(payment_date__gte=sd)
            expenses = expenses.filter(expense_date__gte=sd)

        if ed:
            payments = payments.filter(payment_date__lte=ed)
            expenses = expenses.filter(expense_date__lte=ed)

        payments = payments.order_by('payment_date', 'id')
        expenses = expenses.order_by('expense_date', 'id')

        running_paid = Decimal('0.00')
        running_spent = Decimal('0.00')

        # PAYMENTS
        for p in payments:
            before_paid = running_paid
            running_paid += p.amount

            rows.append({
                'date': p.payment_date,
                'client': client.name,
                'company': client.company.name,
                'budget': client.budget,
                'previous_paid': before_paid,
                'paid_now': p.amount,
                'yet_to_pay': client.budget - running_paid,
                'total_paid': running_paid,
                'spend_detail': '—',
                'salary_info': '—',
                'spend_amount': Decimal('0.00'),
                'balance': running_paid - running_spent,
                'type': 'payment',
            })

        # EXPENSES
        for e in expenses:
            running_spent += e.amount

            if e.category and e.category.name.lower() == 'salary':
                team_name = e.salary_to.name if e.salary_to else ''
                worker_name = e.worker_name.name if e.worker_name else ''
                salary_info = f"{team_name}"
                if worker_name:
                    salary_info += f" / {worker_name}"
            else:
                salary_info = '—'

            rows.append({
                'date': e.expense_date,
                'client': client.name,
                'company': client.company.name,
                'budget': client.budget,
                'previous_paid': running_paid,
                'paid_now': Decimal('0.00'),
                'yet_to_pay': client.budget - running_paid,
                'total_paid': running_paid,
                'spend_detail': e.description,
                'salary_info': salary_info,
                'spend_amount': e.amount,
                'balance': running_paid - running_spent,
                'type': 'expense',
            })

    # =========================
    # TOTAL CALCULATIONS (CORRECT LOCATION)
    # =========================

    total_project_value = Decimal('0.00')
    total_paid = Decimal('0.00')
    total_spend = Decimal('0.00')
    total_yet_to_pay = Decimal('0.00')

    for client in clients:

        client_payments = client.payments.all()
        client_expenses = client.expenses.all()

        if sd:
            client_payments = client_payments.filter(payment_date__gte=sd)
            client_expenses = client_expenses.filter(expense_date__gte=sd)

        if ed:
            client_payments = client_payments.filter(payment_date__lte=ed)
            client_expenses = client_expenses.filter(expense_date__lte=ed)

        client_paid_total = client_payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        client_spend_total = client_expenses.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        total_project_value += client.budget
        total_paid += client_paid_total
        total_spend += client_spend_total
        total_yet_to_pay += (client.budget - client_paid_total)

    grand_balance = total_paid - total_spend

    # =========================
    # FILTER TRANSACTION TYPE
    # =========================
    if txn_type != 'all':
        rows = [r for r in rows if r['type'] == txn_type]

    # SORT
    rows = sorted(
        rows,
        key=lambda x: x['date'],
        reverse=(order == 'new')
    )

    return render(request, 'client/all_clients_statement.html', {
        'rows': rows,
        'start_date': start_date,
        'end_date': end_date,
        'order': order,
        'txn_type': txn_type,
        'total_project_value': total_project_value,
        'total_paid': total_paid,
        'total_spend': total_spend,
        'total_yet_to_pay': total_yet_to_pay,
        'grand_balance': grand_balance,
    })









from decimal import Decimal
from django.http import HttpResponse
from django.utils.dateparse import parse_date

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors


def clean_date(value):
    if not value or value == 'None':
        return None
    return parse_date(value)


from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import PageBreak

def add_page_numbers(canvas, doc):
    canvas.drawRightString(
        820, 15,
        f"Page {doc.page}"
    )



from decimal import Decimal
from django.http import HttpResponse
from django.shortcuts import redirect
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors


def all_client_info_pdf(request):

    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    start_date = clean_date(request.GET.get('start_date'))
    end_date = clean_date(request.GET.get('end_date'))
    order = request.GET.get('order', 'new')
    txn_type = request.GET.get('txn_type', 'all')

    clients = Client.objects.filter(
        company_id=selected_company_id
    ).select_related('company')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="all_clients_statement.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>All Clients Financial Statement</b>", styles['Title']))
    elements.append(Spacer(1, 12))

    table_data = [[
        'Client', 'Company', 'Date',
        'Prev Paid', 'Paid Now', 'Yet To Pay',
        'Spend Detail', 'Spend Amount', 'Balance'
    ]]

    row_styles = []
    row_index = 1

    grand_paid = Decimal('0.00')
    grand_spent = Decimal('0.00')

    for client in clients:

        payments = client.payments.all()
        expenses = client.expenses.all()

        if start_date:
            payments = payments.filter(payment_date__gte=start_date)
            expenses = expenses.filter(expense_date__gte=start_date)

        if end_date:
            payments = payments.filter(payment_date__lte=end_date)
            expenses = expenses.filter(expense_date__lte=end_date)

        ledger = []

        for p in payments:
            ledger.append({
                'type': 'payment',
                'date': p.payment_date,
                'amount': p.amount,
                'obj': p
            })

        for e in expenses:
            ledger.append({
                'type': 'expense',
                'date': e.expense_date,
                'amount': e.amount,
                'obj': e
            })

        ledger = sorted(
            ledger,
            key=lambda x: x['date'],
            reverse=(order == 'new')
        )

        running_paid = Decimal('0.00')
        running_spent = Decimal('0.00')

        for entry in ledger:

            if txn_type != 'all' and entry['type'] != txn_type:
                continue

            prev_paid = running_paid

            if entry['type'] == 'payment':

                running_paid += entry['amount']
                grand_paid += entry['amount']

                yet_to_pay = client.budget - running_paid
                balance = running_paid - running_spent

                table_data.append([
                    client.name,
                    client.company.name,
                    str(entry['date']),
                    f"Rs. {prev_paid:.2f}",
                    f"Rs. {entry['amount']:.2f}",
                    f"Rs. {yet_to_pay:.2f}",
                    '—',
                    '—',
                    f"Rs. {balance:.2f}",
                ])

            else:  # expense

                running_spent += entry['amount']
                grand_spent += entry['amount']

                yet_to_pay = client.budget - running_paid
                balance = running_paid - running_spent

                table_data.append([
                    client.name,
                    client.company.name,
                    str(entry['date']),
                    f"Rs. {prev_paid:.2f}",
                    '—',
                    f"Rs. {yet_to_pay:.2f}",
                    entry['obj'].description,
                    f"Rs. {entry['amount']:.2f}",
                    f"Rs. {balance:.2f}",
                ])

            # 🔴 Highlight negative Yet To Pay (column index 5)
            if yet_to_pay < 0:
                row_styles.append(('TEXTCOLOR', (5, row_index), (5, row_index), colors.red))

            # 🔴 Highlight negative Balance (column index 8)
            if balance < 0:
                row_styles.append(('TEXTCOLOR', (8, row_index), (8, row_index), colors.red))

            row_index += 1

        # =========================
        # CLIENT TOTAL
        # =========================
        client_balance = running_paid - running_spent

        table_data.append([
            f"{client.name} TOTAL", '', '', '',
            f"Rs. {running_paid:.2f}", '',
            '', f"Rs. {running_spent:.2f}",
            f"Rs. {client_balance:.2f}",
        ])

        row_styles.append(('FONTNAME', (0, row_index), (-1, row_index), 'Helvetica-Bold'))

        if client_balance < 0:
            row_styles.append(('TEXTCOLOR', (8, row_index), (8, row_index), colors.red))

        row_index += 1

    # =========================
    # GRAND TOTAL
    # =========================
    grand_balance = grand_paid - grand_spent

    table_data.append([
        'GRAND TOTAL', '', '', '',
        f"Rs. {grand_paid:.2f}", '',
        '', f"Rs. {grand_spent:.2f}",
        f"Rs. {grand_balance:.2f}",
    ])

    row_styles.append(('BACKGROUND', (0, row_index), (-1, row_index), colors.lightgrey))
    row_styles.append(('FONTNAME', (0, row_index), (-1, row_index), 'Helvetica-Bold'))

    if grand_balance < 0:
        row_styles.append(('TEXTCOLOR', (8, row_index), (8, row_index), colors.red))

    # =========================
    # TABLE STYLE
    # =========================
    table = Table(
        table_data,
        repeatRows=1,
        colWidths=[90, 90, 70, 75, 75, 75, 150, 80, 80]
    )

    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (3,1), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ] + row_styles))

    elements.append(table)

    doc.build(
        elements,
        onFirstPage=add_page_numbers,
        onLaterPages=add_page_numbers
    )

    return response











#bank views will be added here


from django.db.models import Sum, Max, Q
from django.utils.timezone import now
from decimal import Decimal
from django.shortcuts import redirect


def bank_index(request):

    # 🏢 COMPANY FROM SESSION
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    # =========================
    # 🔍 FIND BANKS USED BY THIS COMPANY
    # =========================

    banks = Bank.objects.filter(
        company_id=selected_company_id
    )

    # =========================
    # 🔘 FILTERS
    # =========================
    selected_bank = request.GET.get('bank')
    filter_type = request.GET.get('filter_type')
    filter_date = request.GET.get('date')
    filter_month = request.GET.get('month')
    filter_year = request.GET.get('year')

    if selected_bank:
        banks = banks.filter(id=selected_bank)

    total_bank = Decimal('0.00')

    for bank in banks:

        # =========================
        # 📊 BASE QUERYSETS (COMPANY AWARE)
        # =========================
        payments = bank.payments.filter(
            client__company_id=selected_company_id
        )

        expenses = bank.expenses.filter(
            client__company_id=selected_company_id
        )

        # =========================
        # 📅 DATE FILTERS
        # =========================
        if filter_type == 'day' and filter_date:
            payments = payments.filter(payment_date=filter_date)
            expenses = expenses.filter(expense_date=filter_date)

        elif filter_type == 'month' and filter_month and filter_year:
            payments = payments.filter(
                payment_date__month=int(filter_month),
                payment_date__year=int(filter_year)
            )
            expenses = expenses.filter(
                expense_date__month=int(filter_month),
                expense_date__year=int(filter_year)
            )

        elif filter_type == 'year' and filter_year:
            payments = payments.filter(payment_date__year=int(filter_year))
            expenses = expenses.filter(expense_date__year=int(filter_year))

        # =========================
        # 💰 CALCULATIONS
        # =========================
        payment_total = payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        expense_total = expenses.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        bank.filtered_balance = (
            bank.opening_balance + payment_total - expense_total
        )

        # =========================
        # 🗓 LAST TRANSACTION DATE
        # =========================
        last_payment_date = payments.aggregate(
            d=Max('payment_date')
        )['d']

        last_expense_date = expenses.aggregate(
            d=Max('expense_date')
        )['d']

        bank.last_transaction_date = max(
            filter(None, [last_payment_date, last_expense_date]),
            default=None
        )

        total_bank += bank.filtered_balance

    return render(request, 'bank/index.html', {
        'banks': banks,
        'total_bank': total_bank,

        'selected_bank': selected_bank,
        'filter_type': filter_type,
        'filter_date': filter_date,
        'filter_month': filter_month,
        'filter_year': filter_year,

        'months': range(1, 13),
        'current_year': now().year,
    })







from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib import messages


def bank_create(request):

    selected_company_id = request.session.get('selected_company_id')

    if not selected_company_id:
        return redirect('dashboard')

    if request.method == 'POST':

        name = request.POST.get('name', '').strip()
        opening_balance = Decimal(request.POST.get('opening_balance') or 0)

        if not name:
            messages.error(request, "Bank name is required.")
            return redirect('bank_create')

        # 🔐 Prevent duplicate bank inside same company
        if Bank.objects.filter(
            company_id=selected_company_id,
            name__iexact=name
        ).exists():
            messages.error(request, "Bank with this name already exists.")
            return redirect('bank_create')

        Bank.objects.create(
            company_id=selected_company_id,
            name=name,
            opening_balance=opening_balance,
            available_balance=opening_balance
        )

        messages.success(request, "Bank created successfully.")
        return redirect('bank_index')

    return render(request, 'bank/create.html')



from django.shortcuts import get_object_or_404


def bank_update(request, pk):

    selected_company_id = request.session.get('selected_company_id')

    if not selected_company_id:
        return redirect('dashboard')

    # 🔐 Ensure bank belongs to selected company
    bank = get_object_or_404(
        Bank,
        pk=pk,
        company_id=selected_company_id
    )

    if request.method == 'POST':

        name = request.POST.get('name', '').strip()
        opening_balance = Decimal(request.POST.get('opening_balance') or 0)

        if not name:
            messages.error(request, "Bank name is required.")
            return redirect('bank_update', pk=bank.id)

        # 🔐 Prevent duplicate rename
        if Bank.objects.filter(
            company_id=selected_company_id,
            name__iexact=name
        ).exclude(id=bank.id).exists():
            messages.error(request, "Another bank with this name already exists.")
            return redirect('bank_update', pk=bank.id)

        bank.name = name
        bank.opening_balance = opening_balance
        bank.save(update_fields=['name', 'opening_balance'])

        # 🔁 Always recalc after updating opening balance
        bank.recalculate_balance()

        messages.success(request, "Bank updated successfully.")
        return redirect('bank_index')

    return render(request, 'bank/update.html', {
        'bank': bank
    })




def bank_delete(request, pk):
    bank = get_object_or_404(Bank, pk=pk)

    if request.method == 'POST':
        bank.delete()
        return redirect('bank_index')

    return render(request, 'bank/delete.html', {
        'bank': bank
    })





from itertools import chain
from django.db.models import F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.dateparse import parse_date


def bank_log(request, pk):

    # 🏢 COMPANY FROM SESSION
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    bank = get_object_or_404(Bank, pk=pk)

    client_id = request.GET.get('client')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # =========================
    # 📊 BASE QUERYSETS (COMPANY AWARE)
    # =========================
    payments = Payment.objects.filter(
        bank=bank,
        client__company_id=selected_company_id
    ).select_related('client')

    expenses = Expense.objects.filter(
        bank=bank,
        client__company_id=selected_company_id
    ).select_related('client', 'category')

    # =========================
    # 👤 CLIENT FILTER
    # =========================
    if client_id:
        payments = payments.filter(client_id=client_id)
        expenses = expenses.filter(client_id=client_id)

    # =========================
    # 📅 DATE FILTERS
    # =========================
    if start_date:
        sd = parse_date(start_date)
        payments = payments.filter(payment_date__gte=sd)
        expenses = expenses.filter(expense_date__gte=sd)

    if end_date:
        ed = parse_date(end_date)
        payments = payments.filter(payment_date__lte=ed)
        expenses = expenses.filter(expense_date__lte=ed)

    # =========================
    # 🔵 PAYMENTS → CREDIT
    # =========================
    payment_rows = payments.annotate(
        txn_date=F('payment_date'),
        txn_type=Value('Payment'),
        txn_description=Value('Client Payment'),
        category_name=Value('—'),
        credit=F('amount'),
        debit=Value(
            None,
            output_field=DecimalField(max_digits=12, decimal_places=2)
        ),
        client_name=F('client__name'),
    ).values(
        'txn_date',
        'txn_type',
        'txn_description',
        'category_name',
        'credit',
        'debit',
        'client_name',
    )

    # =========================
    # 🔴 EXPENSES → DEBIT
    # =========================
    expense_rows = expenses.annotate(
        txn_date=F('expense_date'),
        txn_type=Value('Spend'),
        txn_description=F('description'),
        category_name=Coalesce(F('category__name'), Value('—')),
        credit=Value(
            None,
            output_field=DecimalField(max_digits=12, decimal_places=2)
        ),
        debit=F('amount'),
        client_name=F('client__name'),
    ).values(
        'txn_date',
        'txn_type',
        'txn_description',
        'category_name',
        'credit',
        'debit',
        'client_name',
    )

    # =========================
    # 🔗 MERGE + SORT
    # =========================
    transactions = sorted(
        chain(payment_rows, expense_rows),
        key=lambda x: x['txn_date']
    )

    # =========================
    # 💰 RUNNING BALANCE
    # =========================
    balance = bank.opening_balance

    for row in transactions:
        if row['credit']:
            balance += row['credit']
        if row['debit']:
            balance -= row['debit']
        row['balance'] = balance

    return render(request, 'bank/bank_log.html', {
        'bank': bank,
        'logs': transactions,

        # 👇 only company clients
        'clients': Client.objects.filter(
            company_id=selected_company_id
        ),

        'selected_client': client_id,
        'start_date': start_date,
        'end_date': end_date,
    })





from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from decimal import Decimal
from django.utils.dateparse import parse_date


def clean_param(value):
    return value if value not in [None, '', 'None'] else None


def bank_log_pdf(request, pk):

    # 🏢 COMPANY FROM SESSION
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    bank = get_object_or_404(Bank, pk=pk)

    # ✅ CLEAN QUERY PARAMS
    client_id = clean_param(request.GET.get('client'))
    start_date = clean_param(request.GET.get('start_date'))
    end_date = clean_param(request.GET.get('end_date'))

    # =========================
    # 📊 BASE QUERYSETS (COMPANY AWARE)
    # =========================
    payments = Payment.objects.filter(
        bank=bank,
        client__company_id=selected_company_id
    ).select_related('client')

    expenses = Expense.objects.filter(
        bank=bank,
        client__company_id=selected_company_id
    ).select_related('client', 'category')

    # 👤 CLIENT FILTER
    if client_id:
        payments = payments.filter(client_id=int(client_id))
        expenses = expenses.filter(client_id=int(client_id))

    # 📅 DATE FILTERS
    if start_date:
        sd = parse_date(start_date)
        payments = payments.filter(payment_date__gte=sd)
        expenses = expenses.filter(expense_date__gte=sd)

    if end_date:
        ed = parse_date(end_date)
        payments = payments.filter(payment_date__lte=ed)
        expenses = expenses.filter(expense_date__lte=ed)

    # =========================
    # 🔁 NORMALIZE TRANSACTIONS
    # =========================
    rows = []

    for p in payments.order_by('payment_date', 'id'):
        rows.append({
            'date': p.payment_date.strftime('%d-%m-%Y'),
            'client': p.client.name,
            'type': 'Payment',
            'desc': 'Client Payment',
            'credit': p.amount,
            'debit': Decimal('0.00'),
        })

    for e in expenses.order_by('expense_date', 'id'):
        rows.append({
            'date': e.expense_date.strftime('%d-%m-%Y'),
            'client': e.client.name,
            'type': 'Spend',
            'desc': e.description,
            'credit': Decimal('0.00'),
            'debit': e.amount,
        })

    rows = sorted(rows, key=lambda x: x['date'])

    # =========================
    # 💰 RUNNING BALANCE
    # =========================
    balance = bank.opening_balance
    for r in rows:
        balance += r['credit']
        balance -= r['debit']
        r['balance'] = balance

    # =========================
    # 📄 PDF GENERATION (LANDSCAPE)
    # =========================
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="{bank.name}_bank_log.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),   # ✅ LANDSCAPE
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()
    elements = []

    # =========================
    # 🧾 HEADER
    # =========================
    elements.append(
        Paragraph(f"<b>Bank Statement – {bank.name}</b>", styles['Title'])
    )

    elements.append(
        Paragraph(
            f"Opening Balance: <b>Rs. {bank.opening_balance:.2f}</b>",
            styles['Normal']
        )
    )

    if start_date or end_date:
        elements.append(
            Paragraph(
                f"Period: {start_date or '—'} to {end_date or '—'}",
                styles['Italic']
            )
        )

    elements.append(Spacer(1, 14))

    # =========================
    # 📊 TABLE
    # =========================
    table_data = [[
        'Date',
        'Client',
        'Type',
        'Description',
        'Credit (Rs.)',
        'Debit (Rs.)',
        'Balance (Rs.)'
    ]]

    for r in rows:
        table_data.append([
            r['date'],
            r['client'],
            r['type'],
            r['desc'],
            f"{r['credit']:.2f}" if r['credit'] else '—',
            f"{r['debit']:.2f}" if r['debit'] else '—',
            f"{r['balance']:.2f}",
        ])

    table = Table(
        table_data,
        repeatRows=1,
        colWidths=[85, 120, 80, 220, 90, 90, 95]
    )

    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8F0FE')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
    ]))

    elements.append(table)

    doc.build(elements)
    return response








#cash views will be added here
from django.utils.timezone import now


from django.utils.timezone import now
from django.utils.dateparse import parse_date
from django.db.models import Sum

def cash_index(request):
    cash_list = Cash.objects.select_related('client')

    # 🔎 FILTER INPUTS
    filter_type = request.GET.get('filter_type')
    filter_date = request.GET.get('date')
    filter_month = request.GET.get('month')
    filter_year = request.GET.get('year')

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    client_id = request.GET.get('client')
    cash_type = request.GET.get('cash_type')  # in / out

    # 👤 CLIENT FILTER
    if client_id:
        cash_list = cash_list.filter(client_id=client_id)

    # 🔄 CASH TYPE FILTER
    if cash_type in [Cash.CASH_IN, Cash.CASH_OUT]:
        cash_list = cash_list.filter(cash_type=cash_type)

    # 📅 DATE RANGE FILTER (PRIORITY)
    if start_date:
        cash_list = cash_list.filter(
            cash_date__gte=parse_date(start_date)
        )

    if end_date:
        cash_list = cash_list.filter(
            cash_date__lte=parse_date(end_date)
        )

    # 📆 DAY / MONTH / YEAR FILTERS (OPTIONAL)
    if filter_type == 'day' and filter_date:
        cash_list = cash_list.filter(cash_date=parse_date(filter_date))

    elif filter_type == 'month' and filter_month and filter_year:
        cash_list = cash_list.filter(
            cash_date__month=int(filter_month),
            cash_date__year=int(filter_year)
        )

    elif filter_type == 'year' and filter_year:
        cash_list = cash_list.filter(
            cash_date__year=int(filter_year)
        )

    cash_list = cash_list.order_by('-cash_date')

    # 💰 TOTAL CASH (FILTERED RESULT)
    cash_in = cash_list.filter(
        cash_type=Cash.CASH_IN
    ).aggregate(total=Sum('amount'))['total'] or 0

    cash_out = cash_list.filter(
        cash_type=Cash.CASH_OUT
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_cash = cash_in - cash_out

    return render(request, 'cash/index.html', {
        'cash_list': cash_list,
        'total_cash': total_cash,

        # filters
        'filter_type': filter_type,
        'filter_date': filter_date,
        'filter_month': filter_month,
        'filter_year': filter_year,
        'start_date': start_date,
        'end_date': end_date,
        'selected_client': client_id,
        'selected_cash_type': cash_type,

        # dropdown data
        'clients': Client.objects.all(),
        'months': range(1, 13),
        'current_year': now().year,
    })



def cash_create(request):
    clients = Client.objects.all()

    if request.method == 'POST':
        client_id = request.POST.get('client')
        amount = Decimal(request.POST.get('amount'))
        cash_type = request.POST.get('cash_type')
        description = request.POST.get('description')
        cash_date = request.POST.get('cash_date')

        if cash_type not in [Cash.CASH_IN, Cash.CASH_OUT]:
            messages.error(request, "Invalid cash type")
            return render(request, 'cash/create.html', {
                'clients': clients
            })

        with transaction.atomic():

            # 🔴 VALIDATE CASH OUT
            if cash_type == Cash.CASH_OUT:
                cash_in = Cash.objects.filter(
                    cash_type=Cash.CASH_IN
                ).aggregate(total=Sum('amount'))['total'] or 0

                cash_out = Cash.objects.filter(
                    cash_type=Cash.CASH_OUT
                ).aggregate(total=Sum('amount'))['total'] or 0

                if cash_in - cash_out < amount:
                    messages.error(request, "Insufficient cash balance")
                    return render(request, 'cash/create.html', {
                        'clients': clients
                    })

            Cash.objects.create(
                client_id=client_id,
                amount=amount,
                cash_type=cash_type,
                description=description,
                cash_date=cash_date
            )

        return redirect('cash_index')

    return render(request, 'cash/create.html', {
        'clients': clients
    })



def cash_update(request, pk):
    cash = get_object_or_404(Cash, pk=pk)
    clients = Client.objects.all()

    old_amount = cash.amount
    old_type = cash.cash_type

    if request.method == 'POST':
        client_id = request.POST.get('client')
        new_amount = Decimal(request.POST.get('amount'))
        new_type = request.POST.get('cash_type')
        description = request.POST.get('description')
        cash_date = request.POST.get('cash_date')

        with transaction.atomic():

            # 🔁 REVERSE OLD EFFECT
            if old_type == Cash.CASH_IN:
                reverse_type = Cash.CASH_OUT
            else:
                reverse_type = Cash.CASH_IN

            Cash.objects.create(
                client=cash.client,
                amount=old_amount,
                cash_type=reverse_type,
                description="Cash update reversal",
                cash_date=cash.cash_date
            )

            # 🔴 VALIDATE NEW CASH OUT
            if new_type == Cash.CASH_OUT:
                cash_in = Cash.objects.filter(
                    cash_type=Cash.CASH_IN
                ).aggregate(total=Sum('amount'))['total'] or 0

                cash_out = Cash.objects.filter(
                    cash_type=Cash.CASH_OUT
                ).aggregate(total=Sum('amount'))['total'] or 0

                if cash_in - cash_out < new_amount:
                    messages.error(request, "Insufficient cash balance")
                    return render(request, 'cash/update.html', {
                        'cash': cash,
                        'clients': clients
                    })

            # 🔁 APPLY NEW ENTRY
            Cash.objects.create(
                client_id=client_id,
                amount=new_amount,
                cash_type=new_type,
                description=description,
                cash_date=cash_date
            )

            # ❌ DELETE OLD ROW (AUDIT PRESERVED VIA REVERSAL)
            cash.delete()

        return redirect('cash_index')

    return render(request, 'cash/update.html', {
        'cash': cash,
        'clients': clients
    })



def cash_delete(request, pk):
    cash = get_object_or_404(Cash, pk=pk)

    if request.method == 'POST':
        with transaction.atomic():
            cash.delete()
        return redirect('cash_index')

    return render(request, 'cash/delete.html', {
        'cash': cash
    })




# available balance views will be added here




from django.db.models import Sum, Max
from django.shortcuts import render, redirect
from decimal import Decimal

from .models import Bank, Payment, Expense


def available_amount(request):

    # 🏢 COMPANY FROM SESSION
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    # =========================
    # 💵 CASH BANK (COMPANY BASED)
    # =========================
    cash_bank = Bank.objects.filter(name__iexact='cash').first()

    total_cash = Decimal('0.00')
    last_cash_date = None

    if cash_bank:
        cash_payments = Payment.objects.filter(
            bank=cash_bank,
            client__company_id=selected_company_id
        )

        cash_expenses = Expense.objects.filter(
            bank=cash_bank,
            client__company_id=selected_company_id
        )

        total_cash = (
            cash_bank.opening_balance
            + (cash_payments.aggregate(t=Sum('amount'))['t'] or Decimal('0.00'))
            - (cash_expenses.aggregate(t=Sum('amount'))['t'] or Decimal('0.00'))
        )

        last_cash_date = max(
            filter(None, [
                cash_payments.aggregate(d=Max('payment_date'))['d'],
                cash_expenses.aggregate(d=Max('expense_date'))['d'],
            ]),
            default=None
        )

    # =========================
    # 🏦 CHEQUE BANKS (ONLY USED BY COMPANY)
    # =========================
    cheque_banks = (
        Bank.objects
        .exclude(name__iexact='cash')
        .filter(
            payments__client__company_id=selected_company_id
        )
        .distinct()
    )

    total_bank = Decimal('0.00')

    for bank in cheque_banks:

        payments = Payment.objects.filter(
            bank=bank,
            client__company_id=selected_company_id
        )

        expenses = Expense.objects.filter(
            bank=bank,
            client__company_id=selected_company_id
        )

        payment_total = payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        expense_total = expenses.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        # ✅ REAL AVAILABLE BALANCE
        bank.available_balance = (
            bank.opening_balance + payment_total - expense_total
        )

        # 🗓 LAST TRANSACTION DATE
        bank.last_transaction_date = max(
            filter(None, [
                payments.aggregate(d=Max('payment_date'))['d'],
                expenses.aggregate(d=Max('expense_date'))['d'],
            ]),
            default=None
        )

        total_bank += bank.available_balance

    return render(request, 'accounts/available_amount.html', {
        'total_cash': total_cash,
        'last_cash_date': last_cash_date,
        'cheque_banks': cheque_banks,
        'total_bank': total_bank,
    })







#payment 

from django.shortcuts import render, redirect
from django.utils.dateparse import parse_date

from .models import Payment, Client, Bank


def payment_index(request):

    # 🏢 COMPANY FROM SESSION
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    client_id = request.GET.get('client')
    mode = request.GET.get('mode')        # cash / cheque
    bank_id = request.GET.get('bank')

    # =========================
    # 📊 BASE QUERYSET (COMPANY AWARE)
    # =========================
    payments = Payment.objects.filter(
        client__company_id=selected_company_id
    ).select_related('client', 'bank')

    # =========================
    # 📅 DATE FILTERS
    # =========================
    if start_date:
        payments = payments.filter(
            payment_date__gte=parse_date(start_date)
        )

    if end_date:
        payments = payments.filter(
            payment_date__lte=parse_date(end_date)
        )

    # =========================
    # 👤 CLIENT FILTER
    # =========================
    if client_id:
        payments = payments.filter(client_id=client_id)

    # =========================
    # 💳 MODE FILTER
    # =========================
    if mode in ['cash', 'cheque']:
        payments = payments.filter(payment_mode=mode)

    # =========================
    # 🏦 BANK FILTER
    # =========================
    if bank_id:
        payments = payments.filter(bank_id=bank_id)

    payments = payments.order_by('-payment_date', '-id')

    # =========================
    # 📥 DROPDOWN DATA (COMPANY AWARE)
    # =========================
    clients = Client.objects.filter(
        company_id=selected_company_id
    )

    cheque_banks = Bank.objects.filter(
        payments__client__company_id=selected_company_id
    ).exclude(
        name__iexact='cash'
    ).distinct()

    cash_bank = Bank.objects.filter(name__iexact='cash').first()

    return render(request, 'payment/index.html', {
        'payments': payments,

        'clients': clients,
        'banks': cheque_banks,
        'cash_bank': cash_bank,

        'start_date': start_date,
        'end_date': end_date,
        'selected_client': client_id,
        'selected_mode': mode,
        'selected_bank': bank_id,
    })








from django.db.models import Sum
from django.contrib import messages
from django.db import transaction
from decimal import Decimal
from django.shortcuts import redirect, render

def payment_create(request):

    selected_company_id = request.session.get('selected_company_id')

    if not selected_company_id:
        return redirect('dashboard')

    clients = Client.objects.filter(company_id=selected_company_id)
    banks = Bank.objects.filter(
        company_id=selected_company_id
    ).order_by('name')


    if request.method == 'POST':

        client_id = request.POST.get('client')
        bank_id = request.POST.get('bank')
        amount = Decimal(request.POST.get('amount'))
        payment_mode = request.POST.get('payment_mode')
        payment_date = request.POST.get('payment_date')

        client = Client.objects.get(
            id=client_id,
            company_id=selected_company_id
        )

        # 🔥 Get total already paid
        total_paid = client.payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        new_total = total_paid + amount

        # ❌ VALIDATION
        if new_total > client.budget:
            messages.error(
                request,
                f"❌ Payment exceeds project value! "
                f"Remaining allowed: ₹ {client.budget - total_paid:,.2f}"
            )
            return render(request, 'payment/create.html', {
                'clients': clients,
                'banks': banks
            })

        with transaction.atomic():

            # 💵 CASH MODE
            if payment_mode == 'cash':
                cash_bank = Bank.objects.get(
                    name__iexact='cash',
                    company_id=selected_company_id
                )

                Payment.objects.create(
                    client=client,
                    bank=cash_bank,
                    amount=amount,
                    payment_mode=Payment.CASH,
                    payment_date=payment_date
                )

                cash_bank.recalculate_balance()

            # 🔵 CHEQUE MODE
            elif payment_mode == 'cheque':

                if not bank_id:
                    messages.error(request, "Select a bank for cheque payment")
                    return render(request, 'payment/create.html', {
                        'clients': clients,
                        'banks': banks
                    })

                bank = Bank.objects.get(
                    id=bank_id,
                    company_id=selected_company_id
                )

                Payment.objects.create(
                    client=client,
                    bank=bank,
                    amount=amount,
                    payment_mode=Payment.CHEQUE,
                    payment_date=payment_date
                )

                bank.recalculate_balance()

        messages.success(request, "✅ Payment added successfully")
        return redirect('payment_index')

    return render(request, 'payment/create.html', {
        'clients': clients,
        'banks': banks
    })








from django.db.models import Sum
from django.contrib import messages
from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect

def payment_update(request, pk):

    selected_company_id = request.session.get('selected_company_id')

    payment = get_object_or_404(
        Payment,
        pk=pk,
        client__company_id=selected_company_id
    )

    clients = Client.objects.filter(company_id=selected_company_id)
    banks = Bank.objects.filter(
        company_id=selected_company_id
    ).order_by('name')


    old_bank = payment.bank

    if request.method == 'POST':

        client_id = request.POST.get('client')
        bank_id = request.POST.get('bank')
        new_amount = Decimal(request.POST.get('amount'))
        new_mode = request.POST.get('payment_mode')
        new_date = request.POST.get('payment_date')

        client = get_object_or_404(
            Client,
            id=client_id,
            company_id=selected_company_id
        )

        # 🔥 Get total paid EXCLUDING this payment
        total_paid = client.payments.exclude(id=payment.id).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        new_total = total_paid + new_amount

        # ❌ VALIDATION
        if new_total > client.budget:
            remaining_allowed = client.budget - total_paid
            messages.error(
                request,
                f"❌ Payment exceeds project value! "
                f"Remaining allowed: ₹ {remaining_allowed:,.2f}"
            )
            return render(request, 'payment/update.html', {
                'payment': payment,
                'clients': clients,
                'banks': banks
            })

        with transaction.atomic():

            # 🔁 Remove old bank effect
            if old_bank:
                old_bank.recalculate_balance()

            # 💵 CASH MODE
            if new_mode == 'cash':
                cash_bank = Bank.objects.get(name__iexact='cash')
                payment.bank = cash_bank
                payment.payment_mode = Payment.CASH

            # 🔵 CHEQUE MODE
            else:
                if not bank_id:
                    messages.error(request, "Select bank for cheque payment")
                    return render(request, 'payment/update.html', {
                        'payment': payment,
                        'clients': clients,
                        'banks': banks
                    })

                payment.bank = Bank.objects.get(id=bank_id)
                payment.payment_mode = Payment.CHEQUE

            payment.client = client
            payment.amount = new_amount
            payment.payment_date = new_date
            payment.save()

            # 🔁 Apply new bank effect
            payment.bank.recalculate_balance()

        messages.success(request, "✅ Payment updated successfully")
        return redirect('payment_index')

    return render(request, 'payment/update.html', {
        'payment': payment,
        'clients': clients,
        'banks': banks
    })





def payment_delete(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    bank = payment.bank

    if request.method == 'POST':
        with transaction.atomic():
            payment.delete()

            if bank:
                bank.recalculate_balance()

        return redirect('payment_index')

    return render(request, 'payment/delete.html', {
        'payment': payment
    })


#worker views will be added here



def worker_index(request):

    # 🏢 COMPANY FROM SESSION
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    # 👷 Workers only for selected company
    workers = (
        Worker.objects
        .filter(company_id=selected_company_id)
        .order_by('name')
    )

    return render(request, 'worker/index.html', {
        'workers': workers
    })



def worker_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        company = request.session.get('selected_company_id')  # 👈 COMPANY FROM SESSION

        if not name:
            messages.error(request, "Worker name is required")
        else:
            Worker.objects.create(name=name, company_id=company)  #👈 ASSOCIATE WITH COMPANY
            messages.success(request, "Worker added successfully")
            return redirect('worker_index')

    return render(request, 'worker/create.html', {
        'title': 'Add Worker',
        'company': Company.objects.get(id=request.session.get('selected_company_id'))
    })



def worker_update(request, pk):
    worker = get_object_or_404(Worker, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name')
        company = request.session.get('selected_company_id')

        if not name:
            messages.error(request, "Worker name is required")
        else:
            worker.name = name
            worker.company_id = company  # Ensure worker remains associated with the company
            worker.save()
            messages.success(request, "Worker updated successfully")
            return redirect('worker_index')

    return render(request, 'worker/update.html', {
        'title': 'Update Worker',
        'worker': worker,
        'company': Company.objects.get(id=request.session.get('selected_company_id'))
    })




def worker_delete(request, pk):
    worker = get_object_or_404(Worker, pk=pk)

    if request.method == 'POST':
        worker.delete()
        messages.success(request, "Worker deleted successfully")
        return redirect('worker_index')

    return render(request, 'worker/delete.html', {
        'worker': worker
    })


def worker_name_index(request):

    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    worker_id = request.GET.get('worker')  # string or None

    # 🏢 Workers of selected company
    workers = Worker.objects.filter(company_id=selected_company_id)

    # 👥 Worker names ONLY under selected company
    names = WorkerName.objects.select_related('worker').filter(
        worker__company_id=selected_company_id
    )

    # 🔎 Apply filter if worker selected
    if worker_id:
        names = names.filter(worker_id=worker_id)

    return render(request, 'worker_name/index.html', {
        'workers': workers,
        'worker_names': names,
        'selected_worker': worker_id,
    })



def worker_name_create(request):

    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    workers = Worker.objects.filter(company_id=selected_company_id)

    if request.method == 'POST':
        worker_id = request.POST.get('worker')
        name = request.POST.get('name', '').strip()

        if not worker_id or not name:
            messages.error(request, "Worker and name are required")
        else:
            WorkerName.objects.create(
                worker_id=worker_id,
                name=name
            )
            messages.success(request, "Worker name added")
            return redirect('worker_name_index')

    return render(request, 'worker_name/create.html', {
        'workers': workers
    })



from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages

def worker_name_update(request, pk):

    # 👤 WorkerName object
    worker_name = get_object_or_404(WorkerName, pk=pk)

    # 🏢 COMPANY FROM SESSION
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    # 👷 Workers under selected company
    workers = Worker.objects.filter(company_id=selected_company_id)

    if request.method == 'POST':
        worker_id = request.POST.get('worker')
        name = request.POST.get('name', '').strip()

        # ❌ Validation
        if not worker_id or not name:
            messages.error(request, "Worker and name are required")
        else:
            # ✅ Ensure worker belongs to same company
            worker = get_object_or_404(
                Worker,
                id=worker_id,
                company_id=selected_company_id
            )

            # ✅ Update
            worker_name.worker = worker
            worker_name.name = name
            worker_name.save()

            messages.success(request, "Worker name updated successfully")
            return redirect('worker_name_index')

    return render(request, 'worker_name/update.html', {
        'worker_name': worker_name,
        'workers': workers,
    })






def worker_name_delete(request, pk):
    worker_name = get_object_or_404(WorkerName, pk=pk)

    if request.method == 'POST':
        worker_name.delete()
        messages.success(request, "Worker name deleted successfully")
        return redirect('worker_name_index')

    return render(request, 'worker_name/delete.html', {
        'worker_name': worker_name
    })



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import ExpenseCategory

# 📄 INDEX
def expense_category_index(request):

    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    categories = ExpenseCategory.objects.filter(
        company_id=selected_company_id
    ).order_by('name')

    return render(request, 'expense_category/index.html', {
        'categories': categories
    })



# ➕ CREATE
def expense_category_create(request):

    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()

        if not name:
            messages.error(request, "Category name is required")
            return redirect('expense_category_create')

        ExpenseCategory.objects.create(
            company_id=selected_company_id,
            name=name
        )

        messages.success(request, "Category created successfully")
        return redirect('expense_category_index')

    return render(request, 'expense_category/create.html')



# ✏️ UPDATE
def expense_category_update(request, pk):

    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    category = get_object_or_404(
        ExpenseCategory,
        pk=pk,
        company_id=selected_company_id
    )

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()

        if not name:
            messages.error(request, "Category name is required")
            return redirect('expense_category_update', pk=pk)

        category.name = name
        category.save()

        messages.success(request, "Category updated successfully")
        return redirect('expense_category_index')

    return render(request, 'expense_category/update.html', {
        'category': category
    })


# 🗑 DELETE
def expense_category_delete(request, pk):
    category = get_object_or_404(ExpenseCategory, pk=pk)

    if request.method == 'POST':
        category.delete()
        messages.success(request, "Category deleted successfully")
        return redirect('expense_category_index')

    return render(request, 'expense_category/delete.html', {
        'category': category
    })




# 📄 INDEX
def expense_subcategory_index(request):

    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    category_id = request.GET.get('category')

    # ✅ COMPANY FILTER
    categories = ExpenseCategory.objects.filter(
        company_id=selected_company_id
    )

    subcategories = ExpenseSubCategory.objects.select_related('category').filter(
        company_id=selected_company_id
    )

    if category_id:
        subcategories = subcategories.filter(category_id=category_id)

    return render(request, 'expense_subcategory/index.html', {
        'categories': categories,
        'subcategories': subcategories,
        'selected_category': category_id,
    })



# ➕ CREATE
def expense_subcategory_create(request):

    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    categories = ExpenseCategory.objects.filter(
        company_id=selected_company_id
    )

    if request.method == 'POST':
        category_id = request.POST.get('category')
        name = request.POST.get('name', '').strip()

        if not category_id or not name:
            messages.error(request, "Category and Sub-category name are required")
        else:
            ExpenseSubCategory.objects.create(
                company_id=selected_company_id,   # ✅ IMPORTANT
                category_id=category_id,
                name=name
            )
            messages.success(request, "Sub-category added successfully")
            return redirect('expense_subcategory_index')

    return render(request, 'expense_subcategory/create.html', {
        'categories': categories
    })



# ✏️ UPDATE
def expense_subcategory_update(request, pk):

    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    subcategory = get_object_or_404(
        ExpenseSubCategory,
        pk=pk,
        company_id=selected_company_id   # ✅ SECURITY
    )

    categories = ExpenseCategory.objects.filter(
        company_id=selected_company_id
    )

    if request.method == 'POST':
        category_id = request.POST.get('category')
        name = request.POST.get('name', '').strip()

        if not name or not category_id:
            messages.error(request, "All fields are required")
        else:
            subcategory.category_id = category_id
            subcategory.name = name
            subcategory.save()

            
            return redirect('expense_subcategory_index')

    return render(request, 'expense_subcategory/update.html', {
        'subcategory': subcategory,
        'categories': categories
    })



# 🗑 DELETE
def expense_subcategory_delete(request, pk):
    subcategory = get_object_or_404(ExpenseSubCategory, pk=pk)

    if request.method == 'POST':
        subcategory.delete()
        messages.success(request, "Sub-category deleted")
        return redirect('expense_subcategory_index')

    return render(request, 'expense_subcategory/delete.html', {
        'subcategory': subcategory
    })



#expense views will be added here

from django.shortcuts import render, redirect
from django.utils.dateparse import parse_date


def expense_index(request):

    # 🏢 COMPANY FROM SESSION
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    # =========================
    # 📊 BASE QUERYSET
    # =========================
    expenses = Expense.objects.select_related(
        'client',
        'bank',
        'category',
        'subcategory',
        'salary_to',
        'worker_name'
    ).filter(
        client__company_id=selected_company_id
    )

    # =========================
    # 🔍 FILTER VALUES
    # =========================
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    client_id = request.GET.get('client')
    category_id = request.GET.get('category')
    subcategory_id = request.GET.get('subcategory')
    spend_mode = request.GET.get('spend_mode')
    bank_id = request.GET.get('bank')
    worker_id = request.GET.get('worker')
    worker_name_id = request.GET.get('worker_name')

    # =========================
    # 📅 DATE FILTERS
    # =========================
    if start_date:
        expenses = expenses.filter(
            expense_date__gte=parse_date(start_date)
        )

    if end_date:
        expenses = expenses.filter(
            expense_date__lte=parse_date(end_date)
        )

    # =========================
    # 👤 CLIENT FILTER
    # =========================
    if client_id:
        expenses = expenses.filter(client_id=client_id)

    # =========================
    # 🏷 CATEGORY FILTER
    # =========================
    if category_id:
        expenses = expenses.filter(category_id=category_id)

    # =========================
    # 🏷 SUBCATEGORY FILTER
    # =========================
    if subcategory_id:
        expenses = expenses.filter(subcategory_id=subcategory_id)

    # =========================
    # 💳 SPEND MODE FILTER
    # =========================
    if spend_mode in ['cash', 'cheque']:
        expenses = expenses.filter(spend_mode=spend_mode)

    # =========================
    # 🏦 BANK FILTER
    # =========================
    if bank_id:
        expenses = expenses.filter(bank_id=bank_id)

    # =========================
    # 👷 SALARY TEAM FILTER
    # =========================
    if worker_id:
        expenses = expenses.filter(salary_to_id=worker_id)

    # =========================
    # 👤 SALARY WORKER NAME FILTER
    # =========================
    if worker_name_id:
        expenses = expenses.filter(worker_name_id=worker_name_id)

    # =========================
    # 📅 ORDERING
    # =========================
    expenses = expenses.order_by('-expense_date')

    # =========================
    # 📋 DROPDOWN DATA
    # =========================
    clients = Client.objects.filter(
        company_id=selected_company_id
    )

    categories = ExpenseCategory.objects.filter(
        company_id=selected_company_id
    )

    subcategories = ExpenseSubCategory.objects.filter(
        category__company_id=selected_company_id
    )

    workers = Worker.objects.filter(
        company_id=selected_company_id
    )

    worker_names = WorkerName.objects.filter(
        worker__company_id=selected_company_id
    ).select_related('worker')

    cash_bank = Bank.objects.filter(
        name__iexact='cash'
    ).first()

    banks = Bank.objects.exclude(
        name__iexact='cash'
    )

    # =========================
    # 📤 RENDER
    # =========================
    return render(request, 'expense/index.html', {
        'expenses': expenses,

        # Selected values (for form state persistence)
        'start_date': start_date,
        'end_date': end_date,
        'selected_client': client_id,
        'selected_category': category_id,
        'selected_subcategory': subcategory_id,
        'selected_spend_mode': spend_mode,
        'selected_bank': bank_id,
        'selected_worker': worker_id,
        'selected_worker_name': worker_name_id,

        # Dropdowns
        'clients': clients,
        'categories': categories,
        'subcategories': subcategories,
        'workers': workers,
        'worker_names': worker_names,
        'cash_bank': cash_bank,
        'banks': banks,
    })




from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils.dateparse import parse_date
from decimal import Decimal


def expense_pdf_export(request):

    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    expenses = Expense.objects.select_related(
        'client',
        'bank',
        'category',
        'subcategory',
        'salary_to',
        'worker_name'
    ).filter(
        client__company_id=selected_company_id
    )

    # =============================
    # FILTERS
    # =============================
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    client_id = request.GET.get('client')
    category_id = request.GET.get('category')
    spend_mode = request.GET.get('spend_mode')
    bank_id = request.GET.get('bank')
    worker_id = request.GET.get('worker')

    if start_date:
        expenses = expenses.filter(expense_date__gte=parse_date(start_date))

    if end_date:
        expenses = expenses.filter(expense_date__lte=parse_date(end_date))

    if client_id:
        expenses = expenses.filter(client_id=client_id)

    if category_id:
        expenses = expenses.filter(category_id=category_id)

    if spend_mode in ['cash', 'cheque']:
        expenses = expenses.filter(spend_mode=spend_mode)

    if bank_id:
        expenses = expenses.filter(bank_id=bank_id)

    if worker_id:
        expenses = expenses.filter(salary_to_id=worker_id)

    expenses = expenses.order_by('expense_date')

    # =============================
    # PDF SETUP
    # =============================
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="expenses_report.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()
    elements = []

    company = Company.objects.get(id=selected_company_id)

    elements.append(Paragraph(
        f"<b>Expense Report – {company.name}</b>",
        styles['Title']
    ))

    if start_date or end_date:
        elements.append(
            Paragraph(
                f"Period: {start_date or '—'} to {end_date or '—'}",
                styles['Italic']
            )
        )

    elements.append(Spacer(1, 15))

    # =============================
    # TABLE DATA
    # =============================
    table_data = [[
        'Date', 'Client', 'Category', 'Sub-Category',
        'Worker Team', 'Worker Name',
        'Mode', 'Bank', 'Amount'
    ]]

    total_amount = Decimal('0.00')

    for e in expenses:

        total_amount += e.amount

        table_data.append([
            e.expense_date.strftime('%d-%m-%Y'),
            e.client.name,
            e.category.name if e.category else '—',
            e.subcategory.name if e.subcategory else '—',
            e.salary_to.name if e.salary_to else '—',
            e.worker_name.name if e.worker_name else '—',
            e.spend_mode.capitalize(),
            e.bank.name if e.bank else 'Cash',
            f"{e.amount:.2f}"
        ])

    table = Table(
        table_data,
        repeatRows=1,
        colWidths=[70, 100, 90, 100, 90, 90, 60, 90, 80]
    )

    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (-1,1), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 15))

    # =============================
    # TOTAL BOX
    # =============================
    total_table = Table(
        [['TOTAL EXPENSE', f"Rs. {total_amount:.2f}"]],
        colWidths=[300, 150]
    )

    total_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))

    elements.append(total_table)

    doc.build(elements)
    return response









from decimal import Decimal
from django.db import transaction
from django.contrib import messages
from django.shortcuts import redirect
from django.db.models import Q

def expense_create(request):

    # 🏢 COMPANY FROM SESSION
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    # =========================
    # 📋 DROPDOWNS (COMPANY AWARE)
    # =========================
    clients = Client.objects.filter(company_id=selected_company_id)

    categories = ExpenseCategory.objects.filter(
        company_id=selected_company_id
    )

    subcategories = ExpenseSubCategory.objects.filter(
        category__company_id=selected_company_id
    )

    workers = Worker.objects.filter(company_id=selected_company_id)

    banks = Bank.objects.filter(
        company_id=selected_company_id
    ).order_by('name')

    cash_bank = Bank.objects.filter(name__iexact='cash').first()

    workers = Worker.objects.filter(company_id=selected_company_id)

    worker_names = WorkerName.objects.filter(
            worker__company_id=selected_company_id
        ).select_related('worker')
    
    # =========================
    # 📩 POST
    # =========================
    if request.method == 'POST':

        client_id = request.POST.get('client')
        bank_id = request.POST.get('bank')
        category_id = request.POST.get('category')
        subcategory_id = request.POST.get('subcategory')
        salary_to_id = request.POST.get('salary_to')
        worker_name_id = request.POST.get('worker_name')
        description = request.POST.get('description', '').strip()
        spend_mode = request.POST.get('spend_mode')
        expense_date = request.POST.get('expense_date')

        try:
            amount = Decimal(request.POST.get('amount'))
        except:
            messages.error(request, "Invalid amount")
            return redirect('expense_create')

        # =========================
        # 🔐 VALIDATIONS
        # =========================
        client = clients.filter(id=client_id).first()
        if not client:
            messages.error(request, "Invalid client")
            return redirect('expense_create')

        category = categories.filter(id=category_id).first() if category_id else None

        subcategory = None
        if subcategory_id:
            subcategory = subcategories.filter(
                id=subcategory_id,
                category_id=category_id
            ).first()

            if not subcategory:
                messages.error(request, "Invalid sub-category selection")
                return redirect('expense_create')

        worker = workers.filter(id=salary_to_id).first() if salary_to_id else None


        with transaction.atomic():

            # 💵 CASH
            if spend_mode == Expense.CASH:
                bank = cash_bank

            # 🏦 CHEQUE
            else:
                bank = banks.filter(id=bank_id).first()
                if not bank:
                    messages.error(request, "Invalid bank")
                    return redirect('expense_create')

            Expense.objects.create(
                client=client,
                bank=bank,
                category=category,
                subcategory=subcategory,
                salary_to=worker,
                worker_name_id=worker_name_id,
                description=description,
                amount=amount,
                spend_mode=spend_mode,
                expense_date=expense_date
            )

            bank.recalculate_balance()

        messages.success(request, "Expense added successfully")
        return redirect('expense_index')

    return render(request, 'expense/create.html', {
        'clients': clients,
        'banks': banks,
        'cash_bank': cash_bank,
        'categories': categories,
        'subcategories': subcategories,
        'workers': workers,
        selected_company_id: selected_company_id,
        'worker_names': worker_names,
    })









from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.contrib import messages
from decimal import Decimal
from django.db.models import Q

def expense_update(request, pk):

    # 🏢 COMPANY FROM SESSION
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    # 🔐 Only allow editing company-related expense
    expense = get_object_or_404(
        Expense,
        pk=pk,
        client__company_id=selected_company_id
    )

    # =========================
    # 📋 DROPDOWNS (COMPANY AWARE)
    # =========================
    clients = Client.objects.filter(company_id=selected_company_id)

    categories = ExpenseCategory.objects.filter(
        company_id=selected_company_id
    )

    subcategories = ExpenseSubCategory.objects.filter(
        category__company_id=selected_company_id
    )

    workers = Worker.objects.filter(company_id=selected_company_id)

    worker_names = WorkerName.objects.filter(
            worker__company_id=selected_company_id
        ).select_related('worker')

    banks = Bank.objects.filter(
        company_id=selected_company_id
    ).order_by('name')

    cash_bank = Bank.objects.filter(name__iexact='cash').first()

    old_bank = expense.bank

    # =========================
    # 📩 POST
    # =========================

    print("POST:", request.POST)

    if request.method == 'POST':

        client_id = request.POST.get('client')
        category_id = request.POST.get('category')
        subcategory_id = request.POST.get('subcategory')
        salary_to_id = request.POST.get('salary_to')
        worker_name_id = request.POST.get('worker_name')
        bank_id = request.POST.get('bank')
        description = request.POST.get('description', '').strip()
        spend_mode = request.POST.get('spend_mode')
        expense_date = request.POST.get('expense_date')

        try:
            new_amount = Decimal(request.POST.get('amount'))
        except:
            messages.error(request, "Invalid amount")
            return redirect('expense_update', pk=pk)

        # 🔐 VALIDATION
        client = clients.filter(id=client_id).first()
        if not client:
            messages.error(request, "Invalid client")
            return redirect('expense_update', pk=pk)

        if category_id:
            category = categories.filter(id=category_id).first()
            if not category:
                messages.error(request, "Invalid category selected")
                return redirect('expense_update', pk=pk)
        else:
            category = expense.category  # KEEP OLD


        if subcategory_id:
            subcategory = subcategories.filter(
                id=subcategory_id,
                category_id=category_id
            ).first()

            if not subcategory:
                messages.error(request, "Invalid sub-category selection")
                return redirect('expense_update', pk=pk)
        else:
            subcategory = expense.subcategory  # KEEP OLD


        worker = None
        worker_name = None

        # Only allow worker fields if category is Salary
        if category and category.name.lower() == "salary":

            if salary_to_id:
                worker = workers.filter(id=salary_to_id).first()
                if not worker:
                    messages.error(request, "Invalid worker team selected")
                    return redirect('expense_update', pk=pk)

            if worker_name_id:
                worker_name = worker_names.filter(
                    id=worker_name_id,
                    worker=worker
                ).first()

                if not worker_name:
                    messages.error(request, "Invalid worker name selected")
                    return redirect('expense_update', pk=pk)

        else:
            # 🚀 Not salary → force remove worker info
            worker = None
            worker_name = None




        with transaction.atomic():

            # 🔁 Reverse old bank effect
            if old_bank:
                old_bank.recalculate_balance()

            # 💵 CASH MODE
            if spend_mode == Expense.CASH:
                bank = cash_bank

            # 🏦 CHEQUE MODE
            else:
                bank = banks.filter(id=bank_id).first()
                if not bank:
                    messages.error(request, "Invalid bank")
                    return redirect('expense_update', pk=pk)

            # 🧾 UPDATE EXPENSE
            expense.client = client
            expense.category = category
            expense.subcategory = subcategory
            expense.salary_to = worker
            expense.worker_name = worker_name
            expense.bank = bank
            expense.description = description
            expense.amount = new_amount
            expense.spend_mode = spend_mode
            expense.expense_date = expense_date
            print("Worker:", worker)
            print("Worker Name:", worker_name)

            expense.save()

            # 🔁 Apply new bank balance
            bank.recalculate_balance()

        messages.success(request, "Expense updated successfully")
        return redirect('expense_index')

    return render(request, 'expense/update.html', {
        'expense': expense,
        'clients': clients,
        'banks': banks,
        'cash_bank': cash_bank,
        'categories': categories,
        'subcategories': subcategories,
        'workers': workers,
        'worker_names': worker_names,
        'selected_company_id': selected_company_id,
    })







from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.db import transaction


def expense_delete(request, pk):

    # 🏢 COMPANY FROM SESSION
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    # 🔒 Only allow deleting expense from selected company
    expense = get_object_or_404(
        Expense,
        pk=pk,
        client__company_id=selected_company_id
    )

    bank = expense.bank

    if request.method == 'POST':
        with transaction.atomic():

            expense.delete()

            # 🔁 Recalculate bank after delete
            if bank:
                bank.recalculate_balance()

        messages.success(request, "Expense deleted successfully")

        return redirect('expense_index')

    return render(request, 'expense/delete.html', {
        'expense': expense
    })





from django.shortcuts import render, redirect
from django.utils.dateparse import parse_date
from django.db.models import Sum
from decimal import Decimal


def salary_index(request):

    # 🏢 COMPANY FROM SESSION
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    # =========================
    # 📊 BASE QUERYSET (ONLY SALARY)
    # =========================
    expenses = Expense.objects.select_related(
        'client', 'bank', 'category', 'salary_to', 'worker_name'
    ).filter(
        client__company_id=selected_company_id,
        category__name__iexact='salary'
    )

    # =========================
    # 🔍 FILTER VALUES
    # =========================
    worker_team_id = request.GET.get('worker')          # Team
    worker_name_id = request.GET.get('worker_name')     # Individual
    client_id = request.GET.get('client')
    spend_mode = request.GET.get('spend_mode')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # =========================
    # 👷 TEAM FILTER
    # =========================
    if worker_team_id:
        expenses = expenses.filter(salary_to_id=worker_team_id)

    # =========================
    # 👷‍♂️ WORKER NAME FILTER
    # =========================
    if worker_name_id:
        expenses = expenses.filter(worker_name_id=worker_name_id)

    # =========================
    # 👤 CLIENT FILTER
    # =========================
    if client_id:
        expenses = expenses.filter(client_id=client_id)

    # =========================
    # 💳 SPEND MODE FILTER
    # =========================
    if spend_mode in ['cash', 'cheque']:
        expenses = expenses.filter(spend_mode=spend_mode)

    # =========================
    # 📅 DATE FILTERS
    # =========================
    if start_date:
        expenses = expenses.filter(expense_date__gte=parse_date(start_date))

    if end_date:
        expenses = expenses.filter(expense_date__lte=parse_date(end_date))

    expenses = expenses.order_by('-expense_date')

    # =========================
    # 💰 TOTAL SALARY
    # =========================
    total_salary = expenses.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    return render(request, 'salary/index.html', {
        'expenses': expenses,
        'total_salary': total_salary,

        # selected filters
        'selected_worker': worker_team_id,
        'selected_worker_name': worker_name_id,
        'selected_client': client_id,
        'selected_spend_mode': spend_mode,
        'start_date': start_date,
        'end_date': end_date,

        # DROPDOWNS
        'workers': Worker.objects.filter(
            company_id=selected_company_id
        ),

        'worker_names': WorkerName.objects.filter(
            worker__company_id=selected_company_id
        ).select_related('worker'),

        'clients': Client.objects.filter(
            company_id=selected_company_id
        ),
    })




from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.dateparse import parse_date
from django.db.models import Sum
from decimal import Decimal

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def salary_pdf(request):

    # =========================
    # 🏢 COMPANY CHECK
    # =========================
    selected_company_id = request.session.get('selected_company_id')
    if not selected_company_id:
        return redirect('dashboard')

    worker_id = request.GET.get('worker')
    worker_name_id = request.GET.get('worker_name')
    client_id = request.GET.get('client')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    spend_mode = request.GET.get('spend_mode')

    # =========================
    # 📊 BASE QUERYSET
    # =========================
    expenses = Expense.objects.select_related(
        'client', 'bank', 'salary_to', 'worker_name', 'category'
    ).filter(
        client__company_id=selected_company_id,
        category__name__iexact='salary'
    )

    # 👷 Worker Team Filter
    if worker_id:
        expenses = expenses.filter(salary_to_id=worker_id)

    # 👤 Worker Name Filter
    if worker_name_id:
        expenses = expenses.filter(worker_name_id=worker_name_id)

    # 👥 Client Filter
    if client_id:
        expenses = expenses.filter(client_id=client_id)

    # 💳 Spend Mode
    if spend_mode in ['cash', 'cheque']:
        expenses = expenses.filter(spend_mode=spend_mode)

    # 📅 Date Filters
    if start_date:
        expenses = expenses.filter(expense_date__gte=parse_date(start_date))

    if end_date:
        expenses = expenses.filter(expense_date__lte=parse_date(end_date))

    expenses = expenses.order_by('expense_date')

    total_salary = expenses.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    # =========================
    # 📄 PDF RESPONSE
    # =========================
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="salary_statement.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=25,
        leftMargin=25,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()
    elements = []

    # =========================
    # 🧾 HEADER
    # =========================
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Title'],
        fontSize=18,
        spaceAfter=6
    )

    elements.append(Paragraph("Salary Statement Report", header_style))
    elements.append(Spacer(1, 6))

    # Dynamic Header Info
    elements.append(Paragraph(
        f"<b>Worker Team:</b> {expenses.first().salary_to.name if expenses and worker_id else 'All'}",
        styles['Normal']
    ))

    elements.append(Paragraph(
        f"<b>Worker Name:</b> {expenses.first().worker_name.name if expenses and worker_name_id else 'All'}",
        styles['Normal']
    ))

    elements.append(Paragraph(
        f"<b>Period:</b> {start_date or '—'} to {end_date or '—'}",
        styles['Normal']
    ))

    elements.append(Spacer(1, 20))

    # =========================
    # 📊 TABLE HEADER
    # =========================
    table_data = [[
        '#', 'Date', 'Client',
        'Team', 'Worker',
        'Mode', 'Description',
        'Bank', 'Amount (Rs)'
    ]]

    # =========================
    # 📄 TABLE ROWS
    # =========================
    for idx, e in enumerate(expenses, start=1):

        table_data.append([
            idx,
            e.expense_date.strftime('%d-%m-%Y'),
            e.client.name if e.client else '—',
            e.salary_to.name if e.salary_to else '—',
            e.worker_name.name if e.worker_name else '—',
            e.spend_mode.capitalize(),
            e.description,
            e.bank.name if e.bank else 'Cash',
            f"{e.amount:,.2f}"
        ])

    table = Table(
        table_data,
        repeatRows=1,
        colWidths=[35, 70, 120, 100, 100, 70, 160, 90, 90]
    )

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E9EFF5')),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),

        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (-1, 1), (-1, -1), 'RIGHT'),

        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 25))

    # =========================
    # 💰 TOTAL BOX
    # =========================
    total_table = Table(
        [['Total Salary Paid', f"Rs. {total_salary:,.2f}"]],
        colWidths=[500, 150]
    )

    total_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F5F7FA')),
        ('GRID', (0, 0), (-1, -1), 0.8, colors.black),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))

    elements.append(total_table)

    doc.build(elements)
    return response








from .models import AppSettings, BackupHistory
from django.core.mail import send_mail
from django.utils.timezone import now
import os
import zipfile
import subprocess
from datetime import timedelta
from django.conf import settings
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect


@login_required
def database_backup(request):
    try:
        now_dt = now()
        month_folder = now_dt.strftime('%Y-%m')
        timestamp = now_dt.strftime('%Y-%m-%d_%H-%M')

        backup_root = os.path.join('/opt/backups/eliteAcc', month_folder)
        os.makedirs(backup_root, exist_ok=True)

        sql_file = os.path.join(
            backup_root,
            f'db_backup_{timestamp}.sql'
        )

        zip_file = os.path.join(
            backup_root,
            f'db_backup_{timestamp}.zip'
        )

        db = settings.DATABASES['default']

        dump_command = [
            "mysqldump",
            "--no-tablespaces",
            f"-u{db['USER']}",
            f"-p{db['PASSWORD']}",
            db['NAME']
        ]

        # 🔹 Create SQL
        with open(sql_file, "w") as f:
            subprocess.run(dump_command, stdout=f, check=True)

        # 🔹 Zip file
        with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(sql_file, arcname=os.path.basename(sql_file))

        os.remove(sql_file)

        # 🔹 Calculate size in MB
        file_size_mb = round(os.path.getsize(zip_file) / (1024 * 1024), 2)

        # 🔹 Save Backup History
        BackupHistory.objects.create(
            file_name=os.path.basename(zip_file),
            file_path=zip_file,
            file_size_mb=file_size_mb,
            created_by=request.user
        )

        # 🔹 Auto delete backups older than 30 days
        cutoff = now() - timedelta(days=30)
        old_backups = BackupHistory.objects.filter(created_at__lt=cutoff)

        for backup in old_backups:
            if os.path.exists(backup.file_path):
                os.remove(backup.file_path)
            backup.delete()

        # 🔹 Send Email Notification
        settings_obj, _ = AppSettings.objects.get_or_create(id=1)

        if settings_obj.notification_email:
            subject = "Elite Accounts - Database Backup Completed"

            message = f"""
Hello Admin,

Your database backup was successfully created.

File: {os.path.basename(zip_file)}
Size: {file_size_mb} MB
Date: {now_dt.strftime('%d-%m-%Y')}
Time: {now_dt.strftime('%H:%M')}

Location:
{zip_file}

Elite Accounts System
"""

            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings_obj.notification_email],
                fail_silently=False
            )

        # 🔹 Download file
        with open(zip_file, 'rb') as f:
            response = HttpResponse(
                f.read(),
                content_type='application/zip'
            )
            response['Content-Disposition'] = (
                f'attachment; filename="{os.path.basename(zip_file)}"'
            )
            return response

    except Exception as e:
        messages.error(request, f"Backup failed: {str(e)}")
        return redirect('settings')



# @login_required
# def database_backup(request):

#     try:
#         now = datetime.now()
#         month_folder = now.strftime('%Y-%m')
#         timestamp = now.strftime('%Y-%m-%d_%H-%M')

#         backup_root = os.path.join('/opt/backups/eliteAcc', month_folder)
#         os.makedirs(backup_root, exist_ok=True)

#         sql_file = os.path.join(
#             backup_root,
#             f'db_backup_{timestamp}.sql'
#         )

#         zip_file = os.path.join(
#             backup_root,
#             f'db_backup_{timestamp}.zip'
#         )

#         db = settings.DATABASES['default']

#         dump_command = [
#             "mysqldump",
#             "--no-tablespaces",
#             f"-u{db['USER']}",
#             f"-p{db['PASSWORD']}",
#             f"-h{db['HOST']}",
#             f"-P{db['PORT']}",
#             db['NAME']
#         ]

#         # Create SQL
#         with open(sql_file, "w", encoding="utf-8") as f:
#             subprocess.run(dump_command, stdout=f, check=True)

#         # Zip it
#         with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
#             zipf.write(sql_file, arcname=os.path.basename(sql_file))

#         os.remove(sql_file)

#         # 🔔 Set session alert
#         request.session['backup_created'] = True

#         # 📥 Download file
#         with open(zip_file, 'rb') as f:
#             response = HttpResponse(f.read(), content_type='application/zip')
#             response['Content-Disposition'] = (
#                 f'attachment; filename="{os.path.basename(zip_file)}"'
#             )
#             return response

#     except Exception as e:
#         messages.error(request, f"Backup failed: {str(e)}")
#         return redirect('settings')


import tempfile
import zipfile
import os
import subprocess
from django.views.decorators.http import require_POST
from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect
from django.conf import settings
from django.core.mail import send_mail
from .models import AppSettings
from django.utils.timezone import now


@login_required
@require_POST
def restore_database(request):
    try:
        uploaded_file = request.FILES.get('backup_file')

        if not uploaded_file:
            messages.error(request, "No file selected.")
            return redirect('settings')

        # 🔒 Logout BEFORE restore
        logout(request)

        restore_time = now()

        # Save temp zip
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_zip:
            for chunk in uploaded_file.chunks():
                temp_zip.write(chunk)
            temp_zip_path = temp_zip.name

        # Extract zip
        with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
            zip_ref.extractall("/tmp")
            extracted_files = zip_ref.namelist()

        sql_filename = extracted_files[0]
        sql_path = os.path.join("/tmp", sql_filename)

        db = settings.DATABASES['default']

        restore_command = [
            "mysql",
            f"-u{db['USER']}",
            f"-p{db['PASSWORD']}",
            db['NAME']
        ]

        with open(sql_path, 'r') as f:
            subprocess.run(restore_command, stdin=f, check=True)

        # 🔔 Send Restore Email
        settings_obj, _ = AppSettings.objects.get_or_create(id=1)

        if settings_obj.notification_email:
            send_mail(
                "Elite Accounts - Database Restored",
                f"""
Hello Admin,

Database was successfully restored.

Date: {restore_time.strftime('%d-%m-%Y')}
Time: {restore_time.strftime('%H:%M')}

Elite Accounts System
                """,
                settings.DEFAULT_FROM_EMAIL,
                [settings_obj.notification_email],
                fail_silently=True
            )

        subprocess.run(["systemctl", "restart", "gunicorn-eliteacc"])

        return redirect('/')

    except Exception as e:
        return redirect(f"/settings/?error={str(e)}")



from .models import AppSettings
from django.contrib import messages

def settings_view(request):
    settings_obj, created = AppSettings.objects.get_or_create(id=1)

    if request.method == 'POST':

        # 🔹 Update email
        settings_obj.notification_email = request.POST.get('notification_email')

        # 🔹 Update favicon (if uploaded)
        if request.FILES.get('favicon'):
            settings_obj.favicon = request.FILES.get('favicon')

        settings_obj.save()

        messages.success(request, "Settings updated successfully!")
        return redirect('settings')

    return render(request, 'settings.html', {
        'settings_obj': settings_obj
    })


@login_required
def backup_history_view(request):
    backups = BackupHistory.objects.order_by('-created_at')

    return render(request, 'backup_history.html', {
        'backups': backups
    })

from django.http import FileResponse, Http404


@login_required
def download_backup(request, backup_id):
    try:
        backup = BackupHistory.objects.get(id=backup_id)

        if not os.path.exists(backup.file_path):
            raise Http404("File not found")

        return FileResponse(
            open(backup.file_path, 'rb'),
            as_attachment=True,
            filename=backup.file_name
        )

    except BackupHistory.DoesNotExist:
        raise Http404("Backup not found")



def help(request):
    return render(request, 'help.html')





#custom error pages


from django.http import HttpResponseBadRequest

def error_404(request, exception):
    return render(request, 'errors/404.html', status=404)
    

def error_500(request):
    return render(request, 'errors/500.html', status=500)

def error_403(request, exception):
    return render(request, 'errors/403.html', status=403)

def error_400(request, exception):
    return render(request, 'errors/400.html', status=400)