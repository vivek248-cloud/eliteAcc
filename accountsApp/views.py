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

        if user is not None and user.is_staff:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid admin credentials")

    return render(request, 'auth/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')







@login_required(login_url='login')
def home(request):
    companies = Company.objects.all().order_by('name')
    selected_company_id = request.GET.get('company')
    selected_bank_id = request.GET.get('bank')   # ✅ NEW

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    clients = Client.objects.none()
    banks = []

    total_cash = Decimal('0.00')
    total_bank = Decimal('0.00')
    total_balance = Decimal('0.00')

    total_payments = Decimal('0.00')   # ✅ FOR TOOLTIP
    total_expenses = Decimal('0.00')   # ✅ FOR TOOLTIP

    selected_bank = None
    display_bank_balance = Decimal('0.00')

    recent_payments = []

    payment_labels = []
    payment_values = []
    expense_labels = []
    expense_values = []

    if selected_company_id:

        # 👥 Clients
        clients = Client.objects.filter(company_id=selected_company_id)

        # 💰 Yet to receive (from all clients)
        total_balance = sum((c.balance() for c in clients), Decimal('0.00'))

        # 🧾 TOTAL PAYMENTS / EXPENSES (FOR TOOLTIP LOGIC)
        total_payments = Payment.objects.filter(
            client__company_id=selected_company_id
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        total_expenses = Expense.objects.filter(
            client__company_id=selected_company_id
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # 💵 CASH BANK
        cash_bank = Bank.objects.filter(name__iexact='cash').first()
        total_cash = cash_bank.available_balance if cash_bank else Decimal('0.00')

        # 🏦 ALL BANKS
        banks = Bank.objects.all()

        total_bank = banks.aggregate(
            total=Sum('available_balance')
        )['total'] or Decimal('0.00')

        # 🏦 BANK SELECTION LOGIC
        if selected_bank_id:
            selected_bank = banks.filter(id=selected_bank_id).first()
            if selected_bank:
                display_bank_balance = selected_bank.available_balance
            else:
                display_bank_balance = total_bank
        else:
            display_bank_balance = total_bank

        # 🧾 Recent payments
        recent_payments = (
            Payment.objects
            .filter(client__company_id=selected_company_id)
            .select_related('client', 'bank')
            .order_by('-payment_date')[:5]
        )

        # 📈 GRAPH DATA
        payment_qs = Payment.objects.filter(client__company_id=selected_company_id)
        expense_qs = Expense.objects.filter(client__company_id=selected_company_id)

        if start_date:
            sd = parse_date(start_date)
            payment_qs = payment_qs.filter(payment_date__gte=sd)
            expense_qs = expense_qs.filter(expense_date__gte=sd)

        if end_date:
            ed = parse_date(end_date)
            payment_qs = payment_qs.filter(payment_date__lte=ed)
            expense_qs = expense_qs.filter(expense_date__lte=ed)

        payment_qs = (
            payment_qs
            .annotate(day=TruncDate('payment_date'))
            .values('day')
            .annotate(total=Sum('amount'))
            .order_by('day')
        )

        expense_qs = (
            expense_qs
            .annotate(day=TruncDate('expense_date'))
            .values('day')
            .annotate(total=Sum('amount'))
            .order_by('day')
        )

        payment_labels, payment_values = fill_date_gaps(payment_qs)
        expense_labels, expense_values = fill_date_gaps(expense_qs)

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

        'start_date': start_date,
        'end_date': end_date,

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

def client_index(request):
    clients = Client.objects.select_related('company').all()

    return render(request, 'client/index.html', {
        'clients': clients
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
    expenses_qs = client.expenses.select_related('bank')

    # 🔍 FILTER VALUES
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    payment_mode = request.GET.get('payment_mode')
    spend_mode = request.GET.get('spend_mode')

    # 📅 DATE FILTERS
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

    # 🔁 ORDER FOR CUMULATIVE CALCULATION
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
        })

    return render(request, 'client/clientinfo.html', {
        'client': client,
        'payments': payment_rows,
        'expenses': expense_rows,

        'start_date': start_date,
        'end_date': end_date,
        'payment_mode': payment_mode,
        'spend_mode': spend_mode,
    })




# export pdf views will be added here



from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from django.http import HttpResponse
from decimal import Decimal
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404

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

    # =========================
    # 💰 PAYMENT CALCULATION
    # =========================
    running_paid = Decimal('0.00')
    payment_rows = []

    for p in payments_qs:
        before = running_paid
        running_paid += p.amount
        remaining = client.budget - running_paid

        payment_rows.append([
            str(p.payment_date),
            f"Rs. {before:.2f}",
            f"Rs. {p.amount:.2f}",
            f"Rs. {remaining:.2f}",
            p.payment_mode.capitalize(),
            p.bank.name if p.bank else 'Cash'
        ])

    total_paid = running_paid

    # =========================
    # 🔴 EXPENSE CALCULATION
    # =========================
    running_spent = Decimal('0.00')
    expense_rows = []

    for e in expenses_qs:
        before = running_spent
        running_spent += e.amount
        remaining = total_paid - running_spent

        expense_rows.append([
            str(e.expense_date),
            e.description,
            f"Rs. {before:.2f}",
            f"Rs. {e.amount:.2f}",
            f"Rs. {remaining:.2f}",
            e.spend_mode.capitalize(),
            e.bank.name if e.bank else 'Cash'
        ])

    # =========================
    # 📄 PDF GENERATION
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

    styles = getSampleStyleSheet()
    elements = []

    # 🔷 HEADER
    elements.append(Paragraph(
        f"<b>Client Statement</b><br/>{client.name} – Project Value Rs. {client.budget:.2f}",
        styles['Title']
    ))
    elements.append(Spacer(1, 12))

    # =========================
    # 💰 PAYMENTS TABLE
    # =========================
    elements.append(Paragraph("<b>Payments</b>", styles['Heading2']))

    payment_table = Table(
        [['Date', 'Before', 'Paid Now', 'Remaining', 'Mode', 'Bank']]
        + payment_rows,
        colWidths=[70, 70, 70, 80, 60, 80]
    )

    payment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    ]))

    elements.append(payment_table)
    elements.append(Spacer(1, 20))

    # =========================
    # 🔴 EXPENSES TABLE
    # =========================
    elements.append(Paragraph("<b>Expenses</b>", styles['Heading2']))

    expense_table = Table(
        [['Date', 'Description', 'Before', 'Spent Now', 'Remaining', 'Mode', 'Bank']]
        + expense_rows,
        colWidths=[65, 120, 65, 70, 75, 55, 65]
    )

    expense_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.pink),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(expense_table)

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


def all_client_info_pdf(request):
    # 🔍 FILTERS
    start_date_raw = request.GET.get('start_date')
    end_date_raw = request.GET.get('end_date')

    start_date = clean_date(start_date_raw)
    end_date = clean_date(end_date_raw)

    order = request.GET.get('order', 'new')          # new | old
    txn_type = request.GET.get('txn_type', 'all')    # all | payment | expense

    clients = Client.objects.select_related('company')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        'attachment; filename="all_clients_statement.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()
    elements = []

    # =========================
    # 🔷 TITLE
    # =========================
    elements.append(Paragraph("<b>All Clients Statement</b>", styles['Title']))
    elements.append(Spacer(1, 10))

    if start_date or end_date:
        elements.append(Paragraph(
            f"Period: {start_date or '—'} to {end_date or '—'}",
            styles['Normal']
        ))
        elements.append(Spacer(1, 12))

    # =========================
    # 🔁 CLIENT LOOP
    # =========================
    for index, client in enumerate(clients):

        payments = client.payments.select_related('bank')
        expenses = client.expenses.select_related('bank')

        # 📅 DATE FILTER
        if start_date:
            payments = payments.filter(payment_date__gte=start_date)
            expenses = expenses.filter(expense_date__gte=start_date)

        if end_date:
            payments = payments.filter(payment_date__lte=end_date)
            expenses = expenses.filter(expense_date__lte=end_date)

        payments = payments.order_by('payment_date', 'id')
        expenses = expenses.order_by('expense_date', 'id')

        rows = []
        running_paid = Decimal('0.00')
        running_spent = Decimal('0.00')

        # 🟢 PAYMENTS
        for p in payments:
            before = running_paid
            running_paid += p.amount

            rows.append({
                'date': p.payment_date,
                'previous_paid': before,
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
        rows = sorted(
            rows,
            key=lambda x: x['date'],
            reverse=(order == 'new')
        )

        if not rows:
            continue

        # =========================
        # 🧾 CLIENT HEADER
        # =========================
        elements.append(Paragraph(
            f"""
            <b>Client:</b> {client.name}<br/>
            <b>Company:</b> {client.company.name if client.company else '—'}<br/>
            <b>Project Value:</b> Rs. {client.budget:.2f}
            """,
            styles['Heading2']
        ))
        elements.append(Spacer(1, 8))

        # =========================
        # 📊 TABLE HEADER
        # =========================
        if txn_type == 'payment':
            table_header = ['Date', 'Previously Paid', 'Paid Now', 'Yet To Pay']

        elif txn_type == 'expense':
            table_header = ['Date', 'Total Paid', 'Spend Details', 'Spend Amount', 'Balance']

        else:  # all
            table_header = [
                'Date',
                'Previously Paid', 'Paid Now', 'Yet To Pay',
                'Spend Details', 'Spend Amount', 'Balance'
            ]

        table_data = [table_header]

        # =========================
        # 📊 TABLE ROWS
        # =========================
        for r in rows:

            if txn_type == 'payment':
                row = [
                    str(r['date']),
                    f"Rs. {r['previous_paid']:.2f}",
                    f"Rs. {r['paid_now']:.2f}",
                    f"Rs. {r['yet_to_pay']:.2f}",
                ]

            elif txn_type == 'expense':
                row = [
                    str(r['date']),
                    f"Rs. {r['total_paid']:.2f}",
                    r['spend_detail'],
                    f"Rs. {r['spend_amount']:.2f}",
                    f"Rs. {r['balance']:.2f}",
                ]

            else:
                row = [
                    str(r['date']),
                    f"Rs. {r['previous_paid']:.2f}",
                    f"Rs. {r['paid_now']:.2f}" if r['paid_now'] else '—',
                    f"Rs. {r['yet_to_pay']:.2f}",
                    r['spend_detail'],
                    f"Rs. {r['spend_amount']:.2f}" if r['spend_amount'] else '—',
                    f"Rs. {r['balance']:.2f}",
                ]

            table_data.append(row)

        # =========================
        # 📄 TABLE RENDER
        # =========================
        table = Table(table_data, repeatRows=1)

        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(table)

        # 🔄 PAGE BREAK (except last client)
        if index < clients.count() - 1:
            elements.append(PageBreak())

    doc.build(elements)
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




def available_amount(request):
    # 🏦 CASH BANK
    cash_bank = Bank.objects.filter(name__iexact='cash').first()
    total_cash = cash_bank.available_balance if cash_bank else 0

    # 🏦 CHEQUE BANKS (EXCLUDE CASH)
    total_bank = Bank.objects.exclude(
        name__iexact='cash'
    ).aggregate(
        total=Sum('available_balance')
    )['total'] or 0

    return render(request, 'accounts/available_amount.html', {
        'total_cash': total_cash,
        'total_bank': total_bank,
    })




#payment 

from itertools import chain
from django.utils.timezone import make_aware
from datetime import datetime

from itertools import chain
from django.utils.dateparse import parse_date

def payment_index(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    client_id = request.GET.get('client')
    mode = request.GET.get('mode')  # cash / cheque

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

    payments = payments.order_by('-payment_date')

    return render(request, 'payment/index.html', {
        'payments': payments,
        'start_date': start_date,
        'end_date': end_date,
        'selected_client': client_id,
        'selected_mode': mode,
        'clients': Client.objects.all(),
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

from django.utils.dateparse import parse_date

def expense_index(request):
    expenses = Expense.objects.select_related(
        'client', 'bank', 'category'
    )

    # 🔍 FILTER VALUES
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    client_id = request.GET.get('client')
    category_id = request.GET.get('category')
    spend_mode = request.GET.get('spend_mode')     # 🆕
    bank_id = request.GET.get('bank')               # 🆕

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

    # 💳 SPEND MODE FILTER (NEW)
    if spend_mode in ['cash', 'cheque']:
        expenses = expenses.filter(spend_mode=spend_mode)

    # 🏦 BANK FILTER (NEW – applies to cheque only)
    if bank_id:
        expenses = expenses.filter(bank_id=bank_id)

    expenses = expenses.order_by('-expense_date')

    return render(request, 'expense/index.html', {
        'expenses': expenses,

        # keep selected values
        'start_date': start_date,
        'end_date': end_date,
        'selected_client': client_id,
        'selected_category': category_id,
        'selected_spend_mode': spend_mode,
        'selected_bank': bank_id,

        # dropdown data
        'clients': Client.objects.all(),
        'categories': ExpenseCategory.objects.all(),
        'banks': Bank.objects.all(),
    })






from decimal import Decimal
from django.db import transaction

def expense_create(request):
    clients = Client.objects.select_related('company')
    banks = Bank.objects.all()
    categories = ExpenseCategory.objects.all()

    if request.method == 'POST':
        client_id = request.POST.get('client')
        bank_id = request.POST.get('bank')
        category_id = request.POST.get('category')
        description = request.POST.get('description')
        amount = Decimal(request.POST.get('amount'))
        spend_mode = request.POST.get('spend_mode')
        expense_date = request.POST.get('expense_date')

        with transaction.atomic():

            # 💵 CASH EXPENSE → BANK = "Cash"
            if spend_mode == Expense.CASH:
                bank = Bank.objects.get(name__iexact='cash')

            # 🔵 CHEQUE EXPENSE
            else:
                if not bank_id:
                    messages.error(request, "Please select a bank")
                    return render(request, 'expense/create.html', {
                        'clients': clients,
                        'banks': banks,
                        'categories': categories
                    })
                bank = Bank.objects.get(id=bank_id)

            # ✅ ALWAYS ALLOW EXPENSE (EVEN IF BALANCE GOES NEGATIVE)
            Expense.objects.create(
                client_id=client_id,
                category_id=category_id,
                bank=bank,
                description=description,
                amount=amount,
                spend_mode=spend_mode,
                expense_date=expense_date
            )

            # 🔁 Recalculate → may become negative
            bank.recalculate_balance()

        return redirect('expense_index')

    return render(request, 'expense/create.html', {
        'clients': clients,
        'banks': banks,
        'categories': categories
    })






from django.shortcuts import get_object_or_404
from django.db import transaction

def expense_update(request, pk):
    expense = get_object_or_404(Expense, pk=pk)

    clients = Client.objects.select_related('company')
    banks = Bank.objects.all()
    categories = ExpenseCategory.objects.all()

    old_bank = expense.bank

    if request.method == 'POST':
        client_id = request.POST.get('client')
        bank_id = request.POST.get('bank')
        category_id = request.POST.get('category')
        description = request.POST.get('description')
        new_amount = Decimal(request.POST.get('amount'))
        spend_mode = request.POST.get('spend_mode')
        expense_date = request.POST.get('expense_date')

        with transaction.atomic():

            # 🔁 REVERSE OLD BANK EFFECT
            if old_bank:
                old_bank.recalculate_balance()

            # 💵 CASH MODE → BANK = "Cash"
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
                        'categories': categories
                    })
                bank = Bank.objects.get(id=bank_id)

            # ✅ ALWAYS ALLOW UPDATE (NEGATIVE BALANCE OK)
            expense.client_id = client_id
            expense.category_id = category_id
            expense.bank = bank
            expense.description = description
            expense.amount = new_amount
            expense.spend_mode = spend_mode
            expense.expense_date = expense_date
            expense.save()

            # 🔁 Recalculate → can go negative
            bank.recalculate_balance()

        return redirect('expense_index')

    return render(request, 'expense/update.html', {
        'expense': expense,
        'clients': clients,
        'banks': banks,
        'categories': categories
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


def help(request):
    return render(request, 'help.html')