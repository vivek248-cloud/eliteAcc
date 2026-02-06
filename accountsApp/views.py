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

from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

def login_view(request):

    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user and user.is_staff:
            login(request, user)

            redirect_to = request.session.pop('last_page', None)

            if redirect_to:
                return redirect(redirect_to)

            return redirect('dashboard')

        messages.error(request, "Invalid credentials")

    return render(request, 'auth/login.html')






def logout_view(request):
    logout(request)
    return redirect('login')






@login_required(login_url='login')
def home(request):
    companies = Company.objects.all().order_by('name')
    selected_company_id = request.GET.get('company') or None
    selected_bank_id = request.GET.get('bank')

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    sd = parse_date(start_date) if start_date else None
    ed = parse_date(end_date) if end_date else None

    clients = Client.objects.none()
    banks = []

    total_cash = Decimal('0.00')
    total_bank = Decimal('0.00')
    total_balance = Decimal('0.00')

    total_payments = Decimal('0.00')
    total_expenses = Decimal('0.00')

    selected_bank = None
    display_bank_balance = Decimal('0.00')

    total_profit = Decimal('0.00')
    profit_percentage = 0
    recent_expenses = (
            Expense.objects
            .filter(client__company_id=selected_company_id)
            .select_related('client', 'category')
            .order_by('-expense_date')[:5]
        )
    
    recent_payments = []

    payment_labels = []
    payment_values = []
    expense_labels = []
    expense_values = []

    all_dates = []
    profit_trend_data = []

    if selected_company_id:

        clients = Client.objects.filter(company_id=selected_company_id)

        # =========================
        # 📊 BASE QUERYSETS (DATE AWARE)
        # =========================
        payment_qs = Payment.objects.filter(client__company_id=selected_company_id)
        expense_qs = Expense.objects.filter(client__company_id=selected_company_id)

        if sd:
            payment_qs = payment_qs.filter(payment_date__gte=sd)
            expense_qs = expense_qs.filter(expense_date__gte=sd)

        if ed:
            payment_qs = payment_qs.filter(payment_date__lte=ed)
            expense_qs = expense_qs.filter(expense_date__lte=ed)

        # =========================
        # 💰 TOTALS
        # =========================
        total_payments = payment_qs.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        total_expenses = expense_qs.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        # =========================
        # 📥 RECEIVABLES (DATE AWARE)
        # =========================
        total_balance = Decimal('0.00')

        for c in clients:
            paid_qs = c.payments.all()

            if sd:
                paid_qs = paid_qs.filter(payment_date__gte=sd)
            if ed:
                paid_qs = paid_qs.filter(payment_date__lte=ed)

            paid_sum = paid_qs.aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')

            total_balance += c.budget - paid_sum

        # =========================
        # 🏦 CASH + BANK
        # =========================
        cash_bank = Bank.objects.filter(name__iexact='cash').first()
        total_cash = cash_bank.available_balance if cash_bank else Decimal('0.00')

        banks = Bank.objects.all()

        for bank in banks:
            bank.available_balance = bank.calculated_balance()

        total_bank = sum(
            (b.available_balance for b in banks),
            Decimal('0.00')
        )


        if selected_bank_id:
            selected_bank = banks.filter(id=selected_bank_id).first()
            display_bank_balance = selected_bank.available_balance if selected_bank else total_bank
        else:
            display_bank_balance = total_bank

        # =========================
        # 📈 PROFIT
        # =========================
        total_profit = total_payments - total_expenses

        if total_payments > 0:
            profit_percentage = (total_profit / total_payments) * 100

        # =========================
        # 🧾 RECENT PAYMENTS (DATE AWARE)
        # =========================
        recent_payments = (
            payment_qs
            .select_related('client', 'bank')
            .order_by('-payment_date')[:5]
        )

        # =========================



        # =========================
        # 📊 GRAPH DATA
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


    return render(request, 'dashboard.html', {
        'companies': companies,
        'selected_company_id': selected_company_id,

        'clients': clients,
        'banks': banks,

        'total_cash': total_cash,
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

        'profit_trend_labels': json.dumps(all_dates),
        'profit_trend_values': json.dumps(profit_trend_data),

        'payment_labels': json.dumps(payment_labels),
        'payment_values': json.dumps(payment_values),
        'expense_labels': json.dumps(expense_labels),
        'expense_values': json.dumps(expense_values),
    })







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

def company_index(request):
    companies = Company.objects.all().order_by('-id')
    return render(request, 'company/index.html', {
        'companies': companies
    })


#create view for Company

def company_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            Company.objects.create(name=name)
            return redirect('company_index')

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
        if name:
            company.name = name
            company.save()
            return redirect('company_index')

    return render(request, 'company/update.html', {
        'company': company
    })


#client views will be added here

from django.db.models import Sum
from decimal import Decimal
from django.db.models import Q

def client_index(request):
    expense_type = request.GET.get('expense_type', 'all')  # business | personal | all
    PERSONAL_CATEGORIES = ['home', 'personal']

    clients = Client.objects.select_related('company')
    client_data = []

    for client in clients:

        payments_total = client.payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        expenses_qs = client.expenses.select_related('category')

        # 🔘 FILTER LOGIC
        if expense_type == 'business':
            # exclude home/personal
            expenses_qs = expenses_qs.exclude(
                Q(category__name__iexact='home') |
                Q(category__name__iexact='personal')
            )

        elif expense_type == 'personal':
            # only home/personal
            expenses_qs = expenses_qs.filter(
                Q(category__name__iexact='home') |
                Q(category__name__iexact='personal')
            )

        # expense_type == 'all' → no filter

        expenses_total = expenses_qs.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        balance = payments_total - expenses_total
        yet_to_pay = client.budget - payments_total

        client_data.append({
            'id': client.id,
            'name': client.name,
            'company': client.company,
            'budget': client.budget,
            'total_paid': payments_total,
            'total_expenses': expenses_total,
            'balance': balance,
            'yet_to_pay': yet_to_pay,
        })

    return render(request, 'client/index.html', {
        'clients': client_data,
        'expense_type': expense_type,
    })






def client_create(request):
    companies = Company.objects.all()

    if request.method == 'POST':
        company_id = request.POST.get('company')
        name = request.POST.get('name')
        budget = request.POST.get('budget')

        if company_id and name and budget:
            Client.objects.create(
                company_id=company_id,
                name=name,
                budget=budget
            )
            return redirect('client_index')

    return render(request, 'client/create.html', {
        'companies': companies
    })




def client_update(request, pk):
    client = get_object_or_404(Client, pk=pk)
    companies = Company.objects.all()

    if request.method == 'POST':
        client.company_id = request.POST.get('company')
        client.name = request.POST.get('name')
        client.budget = request.POST.get('budget')
        client.save()

        return redirect('client_index')

    return render(request, 'client/update.html', {
        'client': client,
        'companies': companies
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
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date

def client_info(request, pk):
    client = get_object_or_404(Client, pk=pk)

    payments_qs = client.payments.select_related('bank')
    expenses_qs = client.expenses.select_related('bank', 'category', 'salary_to')

    # 🔍 FILTER VALUES
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    payment_mode = request.GET.get('payment_mode')
    spend_mode = request.GET.get('spend_mode')
    category_id = request.GET.get('category')
    worker_id = request.GET.get('worker')

    # 📅 DATE FILTERS
    if start_date:
        sd = parse_date(start_date)
        payments_qs = payments_qs.filter(payment_date__gte=sd)
        expenses_qs = expenses_qs.filter(expense_date__gte=sd)

    if end_date:
        ed = parse_date(end_date)
        payments_qs = payments_qs.filter(payment_date__lte=ed)
        expenses_qs = expenses_qs.filter(expense_date__lte=ed)

    # 💳 MODE FILTERS
    if payment_mode:
        payments_qs = payments_qs.filter(payment_mode=payment_mode)

    if spend_mode:
        expenses_qs = expenses_qs.filter(spend_mode=spend_mode)

    # 🏷 CATEGORY FILTER
    if category_id:
        expenses_qs = expenses_qs.filter(category_id=category_id)

    # 👷 WORKER FILTER (salary only)
    if worker_id:
        expenses_qs = expenses_qs.filter(salary_to_id=worker_id)

    # 🔁 ORDER
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
    total_paid = sum(p['amount'] for p in payment_rows)
    running_spent = Decimal('0.00')
    expense_rows = []

    for e in expenses_qs:
        before = running_spent
        running_spent += e.amount
        remaining = total_paid - running_spent

        expense_rows.append({
            'date': e.expense_date,
            'description': e.description,
            'before': before,
            'now': e.amount,
            'remaining': remaining,
            'mode': e.spend_mode,
            'bank': e.bank.name if e.bank else 'Cash',
            'worker': e.salary_to.name if e.salary_to else None,
        })

    return render(request, 'client/clientinfo.html', {
        'client': client,
        'payments': payment_rows,
        'expenses': expense_rows,

        # filters
        'start_date': start_date,
        'end_date': end_date,
        'payment_mode': payment_mode,
        'spend_mode': spend_mode,
        'selected_category': category_id,
        'selected_worker': worker_id,

        # dropdown data
        'categories': ExpenseCategory.objects.all(),
        'workers': Worker.objects.all(),
    })




# export pdf views will be added here



from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from django.http import HttpResponse
from decimal import Decimal
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404
from django.db.models import Sum


def client_info_pdf(request, pk):

    client = get_object_or_404(Client, pk=pk)

    payments_qs = client.payments.select_related('bank')
    expenses_qs = client.expenses.select_related('bank')

    # 🔍 FILTERS
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
            f"Rs. {before:.2f}",
            f"Rs. {p.amount:.2f}",
            f"Rs. {remaining:.2f}",
            p.payment_mode.capitalize(),
            p.bank.name if p.bank else 'Cash'
        ])

    total_paid = running_paid

    # 🏦 Bank wise payment totals
    bank_totals = payments_qs.values('bank__name').annotate(
        total=Sum('amount')
    )

    # =========================
    # 🔴 EXPENSES
    # =========================
    running_spent = Decimal('0.00')
    expense_rows = []

    for e in expenses_qs:
        before = running_spent
        running_spent += e.amount
        remaining = total_paid - running_spent

        expense_rows.append([
            e.expense_date.strftime('%d-%m-%Y'),
            e.description,
            f"Rs. {before:.2f}",
            f"Rs. {e.amount:.2f}",
            f"Rs. {remaining:.2f}",
            e.spend_mode.capitalize(),
            e.bank.name if e.bank else 'Cash'
        ])

    total_spent = running_spent
    final_balance = total_paid - total_spent

    # =========================
    # 📄 PDF SETUP
    # =========================
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{client.name}_statement.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    elements = []

    # =========================
    # 🧾 HEADER
    # =========================
    elements.append(Paragraph("Client Statement", styles['Title']))
    elements.append(
        Paragraph(
            f"{client.name} — Project Value Rs. {client.budget:.2f}",
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

    elements.append(Spacer(1, 12))

    # =========================
    # 💰 PAYMENTS TABLE
    # =========================
    elements.append(Paragraph("Payments", styles['Heading2']))

    payment_table = Table(
        [['Date', 'Before', 'Paid Now', 'Remaining', 'Mode', 'Bank']] + payment_rows,
        colWidths=[65, 70, 70, 80, 55, 75]
    )

    payment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))

    elements.append(payment_table)
    elements.append(Spacer(1, 6))

    elements.append(
        Paragraph(f"<b>Total Paid:</b> Rs. {total_paid:.2f}", styles['Normal'])
    )

    # 🏦 Bank totals display
    for b in bank_totals:
        bank_name = b['bank__name'] or 'Cash'
        elements.append(
            Paragraph(
                f"{bank_name} Total : Rs. {b['total']:.2f}",
                styles['Normal']
            )
        )

    # -------------------------
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("<hr/>", styles['Normal']))
    elements.append(Spacer(1, 12))
    # -------------------------

    # =========================
    # 🔴 EXPENSES TABLE
    # =========================
    elements.append(Paragraph("Expenses", styles['Heading2']))

    expense_table = Table(
        [['Date', 'Description', 'Before', 'Spent', 'Remaining', 'Mode', 'Bank']]
        + expense_rows,
        colWidths=[60, 120, 60, 65, 75, 50, 60]
    )

    expense_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.pink),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))

    elements.append(expense_table)
    elements.append(Spacer(1, 6))

    elements.append(
        Paragraph(f"<b>Total Spent:</b> Rs. {total_spent:.2f}", styles['Normal'])
    )

    elements.append(Spacer(1, 15))

    # =========================
    # 📦 SUMMARY BOX
    # =========================
    summary_table = Table(
        [
            ['TOTAL PAID', f"Rs. {total_paid:.2f}"],
            ['TOTAL SPENT', f"Rs. {total_spent:.2f}"],
            ['FINAL BALANCE', f"Rs. {final_balance:.2f}"],
        ],
        colWidths=[180, 140]
    )

    summary_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('PADDING', (0, 0), (-1, -1), 8),
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
from django.shortcuts import render
from django.utils.dateparse import parse_date
from .models import Client


def all_client_index(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    order = request.GET.get('order', 'new')      # new | old
    txn_type = request.GET.get('txn_type', 'all')  # all | payment | expense

    rows = []

    clients = Client.objects.select_related('company')

    for client in clients:

        payments = client.payments.select_related('bank')
        expenses = client.expenses.select_related('bank')

        # 📅 DATE FILTER
        if start_date:
            sd = parse_date(start_date)
            payments = payments.filter(payment_date__gte=sd)
            expenses = expenses.filter(expense_date__gte=sd)

        if end_date:
            ed = parse_date(end_date)
            payments = payments.filter(payment_date__lte=ed)
            expenses = expenses.filter(expense_date__lte=ed)

        payments = payments.order_by('payment_date', 'id')
        expenses = expenses.order_by('expense_date', 'id')

        running_paid = Decimal('0.00')
        running_spent = Decimal('0.00')

        # 🟢 PAYMENTS
        for p in payments:
            before_paid = running_paid
            running_paid += p.amount

            rows.append({
                'date': p.payment_date,
                'client': client.name,
                'company': client.company.name if client.company else '—',
                'budget': client.budget,

                'previous_paid': before_paid,
                'paid_now': p.amount,
                'yet_to_pay': client.budget - running_paid,

                'total_paid': running_paid,
                'spend_detail': '—',
                'spend_amount': Decimal('0.00'),

                'balance': running_paid - running_spent,
                'type': 'payment',
            })

        # 🔴 EXPENSES
        for e in expenses:
            running_spent += e.amount

            rows.append({
                'date': e.expense_date,
                'client': client.name,
                'company': client.company.name if client.company else '—',
                'budget': client.budget,

                'previous_paid': running_paid,
                'paid_now': Decimal('0.00'),
                'yet_to_pay': client.budget - running_paid,

                'total_paid': running_paid,
                'spend_detail': e.description,
                'spend_amount': e.amount,

                'balance': running_paid - running_spent,
                'type': 'expense',
            })

    # 🔘 TYPE FILTER
    if txn_type != 'all':
        rows = [r for r in rows if r['type'] == txn_type]

    # 🔃 SORT
    rows = sorted(rows, key=lambda x: x['date'], reverse=(order == 'new'))

    return render(request, 'client/all_clients_statement.html', {
        'rows': rows,
        'start_date': start_date,
        'end_date': end_date,
        'order': order,
        'txn_type': txn_type,
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



def all_client_info_pdf(request):

    start_date = clean_date(request.GET.get('start_date'))
    end_date = clean_date(request.GET.get('end_date'))
    order = request.GET.get('order', 'new')
    txn_type = request.GET.get('txn_type', 'all')

    clients = Client.objects.select_related('company')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="all_clients_statement.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),   # ✅ LANDSCAPE MODE
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>All Clients Financial Statement</b>", styles['Title']))

    if start_date or end_date:
        elements.append(
            Paragraph(f"Period: {start_date or '—'} to {end_date or '—'}", styles['Normal'])
        )

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

        running_paid = Decimal('0.00')
        running_spent = Decimal('0.00')

        client_start_row = row_index

        rows = []

        for p in payments.order_by('payment_date', 'id'):
            before = running_paid
            running_paid += p.amount
            grand_paid += p.amount

            rows.append([
                client.name,
                client.company.name if client.company else '—',
                str(p.payment_date),
                f"Rs. {before:.2f}",
                f"Rs. {p.amount:.2f}",
                f"Rs. {client.budget - running_paid:.2f}",
                '—',
                '—',
                f"Rs. {running_paid - running_spent:.2f}",
            ])

        for e in expenses.order_by('expense_date', 'id'):
            running_spent += e.amount
            grand_spent += e.amount

            rows.append([
                client.name,
                client.company.name if client.company else '—',
                str(e.expense_date),
                f"Rs. {running_paid:.2f}",
                '—',
                f"Rs. {client.budget - running_paid:.2f}",
                e.description,
                f"Rs. {e.amount:.2f}",
                f"Rs. {running_paid - running_spent:.2f}",
            ])

        if not rows:
            continue

        for r in rows:
            table_data.append(r)
            row_index += 1

        # 🎨 GROUP BACKGROUND COLOR PER CLIENT
        row_styles.append((
            'BACKGROUND',
            (0, client_start_row),
            (-1, row_index - 1),
            colors.whitesmoke if client_start_row % 2 else colors.transparent
        ))

        # 📊 CLIENT TOTAL ROW
        table_data.append([
            f"{client.name} TOTAL", '', '', '', 
            f"Rs. {running_paid:.2f}", '',
            '', f"Rs. {running_spent:.2f}",
            f"Rs. {running_paid - running_spent:.2f}",
        ])

        row_styles.append((
            'FONTNAME',
            (0, row_index),
            (-1, row_index),
            'Helvetica-Bold'
        ))

        row_index += 1

    # =========================
    # 🧮 GRAND TOTAL
    # =========================
    table_data.append([
        'GRAND TOTAL', '', '', '',
        f"Rs. {grand_paid:.2f}", '',
        '', f"Rs. {grand_spent:.2f}",
        f"Rs. {grand_paid - grand_spent:.2f}",
    ])

    row_styles.append((
        'BACKGROUND',
        (0, row_index),
        (-1, row_index),
        colors.lightgrey
    ))

    row_styles.append((
        'FONTNAME',
        (0, row_index),
        (-1, row_index),
        'Helvetica-Bold'
    ))

    # =========================
    # 📄 TABLE
    # =========================
    table = Table(
        table_data,
        repeatRows=1,
        colWidths=[90, 90, 70, 75, 75, 75, 150, 80, 80]
    )

    base_style = [
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (3,1), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]

    table.setStyle(TableStyle(base_style + row_styles))

    elements.append(table)

    doc.build(elements, onFirstPage=add_page_numbers, onLaterPages=add_page_numbers)

    return response








#bank views will be added here


from django.db.models import Sum
from django.utils.timezone import now

from django.db.models import Sum, Max
from django.utils.timezone import now

def bank_index(request):
    banks = Bank.objects.all()

    selected_bank = request.GET.get('bank')
    filter_type = request.GET.get('filter_type')
    filter_date = request.GET.get('date')
    filter_month = request.GET.get('month')
    filter_year = request.GET.get('year')

    if selected_bank:
        banks = banks.filter(id=selected_bank)

    total_bank = 0

    for bank in banks:
        payments = bank.payments.all()
        expenses = bank.expenses.all()

        # 📅 DATE FILTERS
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

        payment_total = payments.aggregate(total=Sum('amount'))['total'] or 0
        expense_total = expenses.aggregate(total=Sum('amount'))['total'] or 0

        bank.filtered_balance = (
            bank.opening_balance + payment_total - expense_total
        )

        # 🗓 LAST TRANSACTION DATE
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





def bank_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        opening_balance = Decimal(request.POST.get('opening_balance') or 0)

        if name:
            bank = Bank.objects.create(
                name=name,
                opening_balance=opening_balance,
                available_balance=opening_balance  # ✅ SYNC ON CREATE
            )
            return redirect('bank_index')

    return render(request, 'bank/create.html')



def bank_update(request, pk):
    bank = get_object_or_404(Bank, pk=pk)

    if request.method == 'POST':
        bank.name = request.POST.get('name').strip()
        bank.opening_balance = Decimal(
            request.POST.get('opening_balance') or 0
        )

        # ✅ SAVE BASIC FIELDS FIRST
        bank.save(update_fields=['name', 'opening_balance'])

        # ✅ THEN RECALCULATE BALANCE
        bank.recalculate_balance()

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
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_date

def bank_log(request, pk):
    bank = get_object_or_404(Bank, pk=pk)

    client_id = request.GET.get('client')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    payments = Payment.objects.filter(bank=bank).select_related('client')
    expenses = Expense.objects.filter(bank=bank).select_related('client', 'category')

    # 👤 CLIENT FILTER
    if client_id:
        payments = payments.filter(client_id=client_id)
        expenses = expenses.filter(client_id=client_id)

    # 📅 DATE FILTERS
    if start_date:
        sd = parse_date(start_date)
        payments = payments.filter(payment_date__gte=sd)
        expenses = expenses.filter(expense_date__gte=sd)

    if end_date:
        ed = parse_date(end_date)
        payments = payments.filter(payment_date__lte=ed)
        expenses = expenses.filter(expense_date__lte=ed)

    # 🔵 PAYMENTS → CREDIT
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

    # 🔴 EXPENSES → DEBIT
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

    # 🔗 MERGE + SORT
    transactions = sorted(
        chain(payment_rows, expense_rows),
        key=lambda x: x['txn_date']
    )

    # 💰 RUNNING BALANCE
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
        'clients': Client.objects.all(),
        'selected_client': client_id,
        'start_date': start_date,
        'end_date': end_date,
    })



# bank log pdf

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from django.http import HttpResponse
from decimal import Decimal
from itertools import chain
from django.utils.dateparse import parse_date


def clean_param(value):
    return value if value not in [None, '', 'None'] else None


def bank_log_pdf(request, pk):
    bank = get_object_or_404(Bank, pk=pk)

    # ✅ CLEAN QUERY PARAMS
    client_id = clean_param(request.GET.get('client'))
    start_date = clean_param(request.GET.get('start_date'))
    end_date = clean_param(request.GET.get('end_date'))

    payments = Payment.objects.filter(bank=bank).select_related('client')
    expenses = Expense.objects.filter(bank=bank).select_related('client', 'category')

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

    # 🔁 NORMALIZE TRANSACTIONS
    rows = []

    for p in payments:
        rows.append({
            'date': p.payment_date,
            'client': p.client.name,
            'type': 'Payment',
            'desc': 'Client Payment',
            'credit': p.amount,
            'debit': Decimal('0.00'),
        })

    for e in expenses:
        rows.append({
            'date': e.expense_date,
            'client': e.client.name,
            'type': 'Spend',
            'desc': e.description,
            'credit': Decimal('0.00'),
            'debit': e.amount,
        })

    rows = sorted(rows, key=lambda x: x['date'])

    # 💰 RUNNING BALANCE
    balance = bank.opening_balance
    for r in rows:
        balance += r['credit']
        balance -= r['debit']
        r['balance'] = balance

    # =========================
    # 📄 PDF GENERATION
    # =========================
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="{bank.name}_bank_log.pdf"'
    )

    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(
        f"<b>Bank  – {bank.name}</b>",
        styles['Title']
    ))

    elements.append(Paragraph(
        f"Opening Balance: Rs. {bank.opening_balance:.2f}",
        styles['Normal']
    ))

    elements.append(Spacer(1, 12))

    table_data = [[
        'Date', 'Client', 'Type', 'Description',
        'Credit', 'Debit', 'Balance'
    ]]

    for r in rows:
        table_data.append([
            str(r['date']),
            r['client'],
            r['type'],
            r['desc'],
            f"Rs. {r['credit']:.2f}" if r['credit'] else '—',
            f"Rs. {r['debit']:.2f}" if r['debit'] else '—',
            f"Rs. {r['balance']:.2f}",
        ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
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
from django.shortcuts import render
from .models import Bank, Payment

def available_amount(request):

    # 🔁 Recalculate all banks before display
    for bank in Bank.objects.all():
        bank.recalculate_balance()

    # 💵 CASH
    cash_bank = Bank.objects.filter(name__iexact='cash').first()
    total_cash = cash_bank.available_balance if cash_bank else 0

    last_cash_date = None
    if cash_bank:
        last_cash_date = Payment.objects.filter(bank=cash_bank).aggregate(
            latest=Max('payment_date')
        )['latest']

    # 🏦 CHEQUE BANKS
    cheque_banks = Bank.objects.exclude(name__iexact='cash').annotate(
        last_transaction_date=Max('payments__payment_date')
    )

    total_bank = cheque_banks.aggregate(
        total=Sum('available_balance')
    )['total'] or 0

    return render(request, 'accounts/available_amount.html', {
        'total_cash': total_cash,
        'last_cash_date': last_cash_date,
        'cheque_banks': cheque_banks,
        'total_bank': total_bank,
    })






#payment 

from itertools import chain
from django.utils.timezone import make_aware
from datetime import datetime

from itertools import chain
from django.utils.dateparse import parse_date

# def payment_index(request):
#     start_date = request.GET.get('start_date')
#     end_date = request.GET.get('end_date')
#     client_id = request.GET.get('client')
#     mode = request.GET.get('mode')  # cash / cheque

#     payments = Payment.objects.select_related('client', 'bank')

#     # 📅 DATE FILTERS
#     if start_date:
#         payments = payments.filter(payment_date__gte=parse_date(start_date))
#     if end_date:
#         payments = payments.filter(payment_date__lte=parse_date(end_date))

#     # 👤 CLIENT FILTER
#     if client_id:
#         payments = payments.filter(client_id=client_id)

#     # 💳 MODE FILTER
#     if mode in ['cash', 'cheque']:
#         payments = payments.filter(payment_mode=mode)

#     payments = payments.order_by('-payment_date')

#     return render(request, 'payment/index.html', {
#         'payments': payments,
#         'start_date': start_date,
#         'end_date': end_date,
#         'selected_client': client_id,
#         'selected_mode': mode,
#         'clients': Client.objects.all(),
#     })

def payment_index(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    client_id = request.GET.get('client')
    mode = request.GET.get('mode')        # cash / cheque
    bank_id = request.GET.get('bank')

    payments = Payment.objects.select_related('client', 'bank')

    # 📅 DATE FILTERS
    if start_date:
        payments = payments.filter(payment_date__gte=parse_date(start_date))
    if end_date:
        payments = payments.filter(payment_date__lte=parse_date(end_date))

    # 👤 CLIENT FILTER
    if client_id:
        payments = payments.filter(client_id=client_id)

    # 💳 MODE FILTER
    if mode in ['cash', 'cheque']:
        payments = payments.filter(payment_mode=mode)

    # 🏦 BANK FILTER (SAFE)
    if bank_id:
        payments = payments.filter(bank_id=bank_id)

    payments = payments.order_by('-payment_date')

    return render(request, 'payment/index.html', {
        'payments': payments,
        'clients': Client.objects.select_related('company'),  # ✅ IMPORTANT,

        'banks': Bank.objects.exclude(name__iexact='cash'),   # cheque banks
        'cash_bank': Bank.objects.filter(name__iexact='cash').first(),

        'start_date': start_date,
        'end_date': end_date,
        'selected_client': client_id,
        'selected_mode': mode,
        'selected_bank': bank_id,
    })





from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction



def payment_create(request):
    # clients = Client.objects.all()
    clients = Client.objects.select_related('company')  # ✅ IMPORTANT
    banks = Bank.objects.all()

    if request.method == 'POST':
        client_id = request.POST.get('client')
        bank_id = request.POST.get('bank')
        amount = Decimal(request.POST.get('amount'))
        payment_mode = request.POST.get('payment_mode')
        payment_date = request.POST.get('payment_date')

        with transaction.atomic():

            # 💵 CASH PAYMENT → BANK = "Cash"
            if payment_mode == 'cash':
                cash_bank = Bank.objects.get(name__iexact='cash')

                Payment.objects.create(
                    client_id=client_id,
                    bank=cash_bank,
                    amount=amount,
                    payment_mode=Payment.CASH,
                    payment_date=payment_date
                )

                cash_bank.recalculate_balance()

            # 🔵 CHEQUE PAYMENT
            elif payment_mode == 'cheque':
                if not bank_id:
                    messages.error(request, "Select a bank for cheque payment")
                    return render(request, 'payment/create.html', {
                        'clients': clients,
                        'banks': banks
                    })

                bank = Bank.objects.get(id=bank_id)

                Payment.objects.create(
                    client_id=client_id,
                    bank=bank,
                    amount=amount,
                    payment_mode=Payment.CHEQUE,
                    payment_date=payment_date
                )

                bank.recalculate_balance()

        return redirect('payment_index')

    return render(request, 'payment/create.html', {
        'clients': clients,
        'banks': banks
    })







from django.db import transaction

from django.shortcuts import get_object_or_404
from django.db import transaction

def payment_update(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    # clients = Client.objects.all()
    clients = Client.objects.select_related('company')  # ✅ IMPORTANT
    banks = Bank.objects.all()

    old_bank = payment.bank

    if request.method == 'POST':
        client_id = request.POST.get('client')
        bank_id = request.POST.get('bank')
        new_amount = Decimal(request.POST.get('amount'))
        new_mode = request.POST.get('payment_mode')
        new_date = request.POST.get('payment_date')

        with transaction.atomic():

            # 🔁 REMOVE OLD BANK EFFECT
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

            payment.client_id = client_id
            payment.amount = new_amount
            payment.payment_date = new_date
            payment.save()

            # 🔁 APPLY NEW BANK EFFECT
            payment.bank.recalculate_balance()

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
    workers = Worker.objects.all().order_by('name')
    return render(request, 'worker/index.html', {
        'workers': workers
    })



def worker_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')

        if not name:
            messages.error(request, "Worker name is required")
        else:
            Worker.objects.create(name=name)
            messages.success(request, "Worker added successfully")
            return redirect('worker_index')

    return render(request, 'worker/create.html', {
        'title': 'Add Worker'
    })



def worker_update(request, pk):
    worker = get_object_or_404(Worker, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name')

        if not name:
            messages.error(request, "Worker name is required")
        else:
            worker.name = name
            worker.save()
            messages.success(request, "Worker updated successfully")
            return redirect('worker_index')

    return render(request, 'worker/update.html', {
        'title': 'Update Worker',
        'worker': worker
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










from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import ExpenseCategory

# 📄 INDEX
def expense_category_index(request):
    categories = ExpenseCategory.objects.order_by('name')
    return render(request, 'expense_category/index.html', {
        'categories': categories
    })


# ➕ CREATE
def expense_category_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')

        if not name:
            messages.error(request, "Category name is required")
            return redirect('expense_category_create')

        ExpenseCategory.objects.create(name=name)
        messages.success(request, "Category created successfully")
        return redirect('expense_category_index')

    return render(request, 'expense_category/create.html')


# ✏️ UPDATE
def expense_category_update(request, pk):
    category = get_object_or_404(ExpenseCategory, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name')

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





#expense views will be added here

from django.utils.dateparse import parse_date



def expense_index(request):

    expenses = Expense.objects.select_related(
        'client', 'bank', 'category', 'salary_to'
    )

    # 🔍 FILTER VALUES
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    client_id = request.GET.get('client')
    category_id = request.GET.get('category')
    spend_mode = request.GET.get('spend_mode')
    bank_id = request.GET.get('bank')
    worker_id = request.GET.get('worker')   # 👈 NEW

    # 📅 DATE FILTERS
    if start_date:
        expenses = expenses.filter(expense_date__gte=parse_date(start_date))
    if end_date:
        expenses = expenses.filter(expense_date__lte=parse_date(end_date))

    # 👤 CLIENT FILTER
    if client_id:
        expenses = expenses.filter(client_id=client_id)

    # 🏷 CATEGORY FILTER
    if category_id:
        expenses = expenses.filter(category_id=category_id)

    # 💳 SPEND MODE FILTER
    if spend_mode in ['cash', 'cheque']:
        expenses = expenses.filter(spend_mode=spend_mode)

    # 🏦 BANK FILTER
    if bank_id:
        expenses = expenses.filter(bank_id=bank_id)

    # 👷 WORKER FILTER (NEW)
    if worker_id:
        expenses = expenses.filter(salary_to_id=worker_id)

    expenses = expenses.order_by('-expense_date')

    return render(request, 'expense/index.html', {
        'expenses': expenses,

        # selected values
        'start_date': start_date,
        'end_date': end_date,
        'selected_client': client_id,
        'selected_category': category_id,
        'selected_spend_mode': spend_mode,
        'selected_bank': bank_id,
        'selected_worker': worker_id,   # 👈 NEW

        # dropdown data
        'clients': Client.objects.select_related('company'),
        'categories': ExpenseCategory.objects.all(),
        'workers': Worker.objects.all(),    # 👈 NEW

        'cash_bank': Bank.objects.filter(name__iexact='cash').first(),
        'banks': Bank.objects.exclude(name__iexact='cash'),
    })



from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from decimal import Decimal


def expense_pdf_export(request):

    expenses = Expense.objects.select_related(
        'client', 'bank', 'category', 'salary_to'
    )

    # 🔍 SAME FILTERS
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

    # =====================
    # 📄 PDF SETUP
    # =====================
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="expenses_report.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()
    elements = []

    # =====================
    # 🧾 HEADER
    # =====================
    elements.append(Paragraph("Expense Report", styles['Title']))

    if start_date or end_date:
        elements.append(
            Paragraph(
                f"Period: {start_date or '—'} to {end_date or '—'}",
                styles['Italic']
            )
        )

    elements.append(Spacer(1, 10))

    # =====================
    # 📊 TABLE DATA
    # =====================
    table_data = [[
        'Date', 'Client', 'Category', 'Worker',
        'Mode', 'Bank', 'Amount'
    ]]

    total_amount = Decimal('0.00')

    for e in expenses:
        total_amount += e.amount

        table_data.append([
            e.expense_date.strftime('%d-%m-%Y'),
            e.client.name,
            e.category.name if e.category else '—',
            e.salary_to.name if e.salary_to else '—',
            e.spend_mode.capitalize(),
            e.bank.name if e.bank else 'Cash',
            f"{e.amount:.2f}"
        ])

    # =====================
    # 📄 TABLE
    # =====================
    table = Table(
        table_data,
        colWidths=[65, 80, 70, 70, 55, 70, 65],
        repeatRows=1
    )

    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (-1,1), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 12))

    # =====================
    # 💰 TOTAL BOX
    # =====================
    total_table = Table(
        [['TOTAL EXPENSE', f"Rs. {total_amount:.2f}"]],
        colWidths=[200, 120]
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

def expense_create(request):
    clients = Client.objects.select_related('company')
    banks = Bank.objects.all()
    categories = ExpenseCategory.objects.all()
    workers = Worker.objects.all()   # ✅ NEW

    if request.method == 'POST':
        client_id = request.POST.get('client')
        bank_id = request.POST.get('bank')
        category_id = request.POST.get('category')
        salary_to_id = request.POST.get('salary_to')   # ✅ NEW
        description = request.POST.get('description')
        amount = Decimal(request.POST.get('amount'))
        spend_mode = request.POST.get('spend_mode')
        expense_date = request.POST.get('expense_date')

        with transaction.atomic():

            # 💵 CASH
            if spend_mode == Expense.CASH:
                bank = Bank.objects.get(name__iexact='cash')
            else:
                if not bank_id:
                    messages.error(request, "Please select a bank")
                    return render(request, 'expense/create.html', {
                        'clients': clients,
                        'banks': banks,
                        'categories': categories,
                        'workers': workers
                    })
                bank = Bank.objects.get(id=bank_id)

            Expense.objects.create(
                client_id=client_id,
                category_id=category_id,
                salary_to_id=salary_to_id if salary_to_id else None,  # ✅
                bank=bank,
                description=description,
                amount=amount,
                spend_mode=spend_mode,
                expense_date=expense_date
            )

            bank.recalculate_balance()

        return redirect('expense_index')

    return render(request, 'expense/create.html', {
        'clients': clients,
        'banks': banks,
        'categories': categories,
        'workers': workers   # ✅
    })





# from django.shortcuts import get_object_or_404
# from django.db import transaction

# def expense_update(request, pk):
#     expense = get_object_or_404(Expense, pk=pk)

#     clients = Client.objects.select_related('company')
#     banks = Bank.objects.all()
#     categories = ExpenseCategory.objects.all()

#     old_bank = expense.bank

#     if request.method == 'POST':
#         client_id = request.POST.get('client')
#         bank_id = request.POST.get('bank')
#         category_id = request.POST.get('category')
#         description = request.POST.get('description')
#         new_amount = Decimal(request.POST.get('amount'))
#         spend_mode = request.POST.get('spend_mode')
#         expense_date = request.POST.get('expense_date')

#         with transaction.atomic():

#             # 🔁 REVERSE OLD BANK EFFECT
#             if old_bank:
#                 old_bank.recalculate_balance()

#             # 💵 CASH MODE → BANK = "Cash"
#             if spend_mode == Expense.CASH:
#                 bank = Bank.objects.get(name__iexact='cash')

#             # 🔵 CHEQUE MODE
#             else:
#                 if not bank_id:
#                     messages.error(request, "Please select a bank")
#                     return render(request, 'expense/update.html', {
#                         'expense': expense,
#                         'clients': clients,
#                         'banks': banks,
#                         'categories': categories
#                     })
#                 bank = Bank.objects.get(id=bank_id)

#             # ✅ ALWAYS ALLOW UPDATE (NEGATIVE BALANCE OK)
#             expense.client_id = client_id
#             expense.category_id = category_id
#             expense.bank = bank
#             expense.description = description
#             expense.amount = new_amount
#             expense.spend_mode = spend_mode
#             expense.expense_date = expense_date
#             expense.save()

#             # 🔁 Recalculate → can go negative
#             bank.recalculate_balance()

#         return redirect('expense_index')

#     return render(request, 'expense/update.html', {
#         'expense': expense,
#         'clients': clients,
#         'banks': banks,
#         'categories': categories
#     })




from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.contrib import messages
from decimal import Decimal

def expense_update(request, pk):
    expense = get_object_or_404(Expense, pk=pk)

    clients = Client.objects.select_related('company')
    banks = Bank.objects.all()
    categories = ExpenseCategory.objects.all()
    workers = Worker.objects.all()   # ✅ NEW

    old_bank = expense.bank

    if request.method == 'POST':
        client_id = request.POST.get('client')
        bank_id = request.POST.get('bank')
        category_id = request.POST.get('category')
        salary_to_id = request.POST.get('salary_to')  # ✅ NEW
        description = request.POST.get('description')
        new_amount = Decimal(request.POST.get('amount'))
        spend_mode = request.POST.get('spend_mode')
        expense_date = request.POST.get('expense_date')

        with transaction.atomic():

            # 🔁 REVERSE OLD BANK EFFECT
            if old_bank:
                old_bank.recalculate_balance()

            # 💵 CASH MODE → BANK = Cash
            if spend_mode == Expense.CASH:
                bank = Bank.objects.get(name__iexact='cash')

            # 🔵 CHEQUE MODE
            else:
                if not bank_id:
                    messages.error(request, "Please select a bank")
                    return render(request, 'expense/update.html', {
                        'expense': expense,
                        'clients': clients,
                        'banks': banks,
                        'categories': categories,
                        'workers': workers
                    })
                bank = Bank.objects.get(id=bank_id)

            # 🧾 UPDATE EXPENSE
            expense.client_id = client_id
            expense.category_id = category_id
            expense.salary_to_id = salary_to_id if salary_to_id else None  # ✅
            expense.bank = bank
            expense.description = description
            expense.amount = new_amount
            expense.spend_mode = spend_mode
            expense.expense_date = expense_date
            expense.save()

            # 🔁 APPLY NEW BANK EFFECT
            bank.recalculate_balance()

        return redirect('expense_index')

    return render(request, 'expense/update.html', {
        'expense': expense,
        'clients': clients,
        'banks': banks,
        'categories': categories,
        'workers': workers   # ✅
    })





def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    bank = expense.bank

    if request.method == 'POST':
        with transaction.atomic():
            expense.delete()

            if bank:
                bank.recalculate_balance()

        return redirect('expense_index')

    return render(request, 'expense/delete.html', {
        'expense': expense
    })




from django.shortcuts import render
from django.utils.dateparse import parse_date
from django.db.models import Sum
from decimal import Decimal

def salary_index(request):

    expenses = Expense.objects.select_related(
        'client', 'bank', 'category', 'salary_to'
    ).filter(
        category__name__iexact='salary'
    )

    # 🔍 FILTER VALUES
    worker_id = request.GET.get('worker')
    client_id = request.GET.get('client')
    spend_mode = request.GET.get('spend_mode')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # 👷 WORKER FILTER
    if worker_id:
        expenses = expenses.filter(salary_to_id=worker_id)

    # 👤 CLIENT FILTER
    if client_id:
        expenses = expenses.filter(client_id=client_id)

    # 💳 SPEND MODE FILTER
    if spend_mode in ['cash', 'cheque']:
        expenses = expenses.filter(spend_mode=spend_mode)

    # 📅 DATE FILTERS
    if start_date:
        expenses = expenses.filter(expense_date__gte=parse_date(start_date))
    if end_date:
        expenses = expenses.filter(expense_date__lte=parse_date(end_date))

    expenses = expenses.order_by('-expense_date')

    total_salary = expenses.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    return render(request, 'salary/index.html', {
        'expenses': expenses,
        'total_salary': total_salary,

        # filters
        'selected_worker': worker_id,
        'selected_client': client_id,
        'selected_spend_mode': spend_mode,
        'start_date': start_date,
        'end_date': end_date,

        # dropdown data
        'workers': Worker.objects.all(),
        'clients': Client.objects.select_related('company'),
    })


from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django.db.models import Sum
from decimal import Decimal

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors


def salary_pdf(request):

    worker_id = request.GET.get('worker')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    spend_mode = request.GET.get('spend_mode')

    if not worker_id:
        return HttpResponse("Worker is required", status=400)

    worker = get_object_or_404(Worker, id=worker_id)

    expenses = Expense.objects.select_related(
        'client', 'bank', 'salary_to', 'category'
    ).filter(
        category__name__iexact='salary',
        salary_to_id=worker_id
    )

    # 💳 SPEND MODE
    if spend_mode in ['cash', 'cheque']:
        expenses = expenses.filter(spend_mode=spend_mode)

    # 📅 DATE FILTERS
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
    response['Content-Disposition'] = (
        f'attachment; filename="salary_{worker.name}.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    elements = []

    # =========================
    # 🧾 HEADER
    # =========================
    elements.append(
        Paragraph("<b>Salary Statement</b>", styles['Title'])
    )
    elements.append(Spacer(1, 6))

    elements.append(
        Paragraph(
            f"<b>Worker:</b> {worker.name}",
            styles['Normal']
        )
    )

    if hasattr(worker, 'role') and worker.role:
        elements.append(
            Paragraph(
                f"<b>Role:</b> {worker.role}",
                styles['Normal']
            )
        )

    # =========================
    # 📅 PERIOD DISPLAY
    # =========================
    if start_date and end_date:
        period_text = f"{start_date} to {end_date}"
    elif start_date:
        period_text = f"From {start_date}"
    elif end_date:
        period_text = f"Up to {end_date}"
    else:
        period_text = "All time"

    elements.append(
        Paragraph(
            f"<b>Period:</b> {period_text}",
            styles['Normal']
        )
    )


    elements.append(Spacer(1, 15))

    # =========================
    # 📊 TABLE DATA
    # =========================
    table_data = [
        ['#', 'Date', 'Client', 'Mode', 'Description', 'Bank', 'Amount (Rs.)']
    ]

    for idx, e in enumerate(expenses, start=1):
        table_data.append([
            idx,
            e.expense_date.strftime('%d-%m-%Y'),
            e.client.name if e.client else '—',
            e.spend_mode.capitalize(),
            e.description,
            e.bank.name if e.bank else 'Cash',
            f"{e.amount:.2f}"
        ])

    table = Table(
        table_data,
        colWidths=[30, 70, 90, 60, 100, 70, 80],
        repeatRows=1
    )

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),

        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (-1, 1), (-1, -1), 'RIGHT'),

        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    # =========================
    # 💰 TOTAL BOX
    # =========================
    total_table = Table(
        [['Total Salary Paid', f"Rs. {total_salary:.2f}"]],
        colWidths=[300, 120]
    )

    total_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.8, colors.black),
        ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))

    elements.append(total_table)

    doc.build(elements)
    return response







import os
import zipfile
import subprocess
from datetime import datetime
from django.conf import settings
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required


@login_required
def database_backup(request):

    now = datetime.now()
    month_folder = now.strftime('%Y-%m')
    timestamp = now.strftime('%Y-%m-%d_%H-%M')

    backup_root = os.path.join(settings.BASE_DIR, 'backups', month_folder)
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

    # 🔥 MYSQLDUMP COMMAND
    dump_command = [
        "mysqldump",
        f"-u{db['USER']}",
        f"-p{db['PASSWORD']}",
        f"-h{db['HOST']}",
        f"-P{db['PORT']}",
        db['NAME']
    ]

    # 📄 Create .sql backup
    with open(sql_file, "w", encoding="utf-8") as f:
        subprocess.run(dump_command, stdout=f, check=True)

    # 🗜 Zip it
    with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(sql_file, arcname=os.path.basename(sql_file))

    # ❌ remove raw sql (optional)
    os.remove(sql_file)

    # 📤 download zip
    with open(zip_file, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/zip')
        response['Content-Disposition'] = (
            f'attachment; filename="{os.path.basename(zip_file)}"'
        )

    return response





from .models import AppSettings
from django.contrib import messages

def settings_view(request):

    settings_obj, created = AppSettings.objects.get_or_create(id=1)

    if request.method == 'POST':
        email = request.POST.get('notification_email')

        settings_obj.notification_email = email
        settings_obj.save()

        messages.success(request, "Notification email updated successfully!")

    return render(request, 'settings.html', {
        'settings_obj': settings_obj
    })





def help(request):
    return render(request, 'help.html')