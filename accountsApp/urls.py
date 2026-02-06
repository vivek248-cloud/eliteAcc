from django.urls import path
from .views import *
from django.contrib.auth import views as auth_views

urlpatterns = [
    

    path('', login_view, name='login'),
    path('dashboard/', home, name='dashboard'),
    path('logout/', logout_view, name='logout'),

    path('companies/', company_index, name='company_index'),
    path('companies/create/', company_create, name='company_create'),
    path('companies/update/<int:pk>/', company_update, name='company_update'),
    path('companies/delete/<int:pk>/', company_delete, name='company_delete'),


    path('clients/', client_index, name='client_index'),
    path('clients/create/', client_create, name='client_create'),
    path('clients/update/<int:pk>/', client_update, name='client_update'),
    path('clients/delete/<int:pk>/', client_delete, name='client_delete'),
    path('clients/<int:pk>/', client_info, name='client_info'),
    path('clients/<int:pk>/export/pdf/', client_info_pdf, name='client_info_pdf'),
    path('clients/all/', all_client_index, name='all_clients_statement'),
    path('clients/pdf/', all_client_info_pdf, name='all_client_info_pdf'),



    path('banks/', bank_index, name='bank_index'),
    path('banks/create/', bank_create, name='bank_create'),
    path('banks/update/<int:pk>/', bank_update, name='bank_update'),
    path('banks/delete/<int:pk>/', bank_delete, name='bank_delete'),
    path('banks/<int:pk>/log/', bank_log, name='bank_log'),
    path('banks/<int:pk>/log/pdf/', bank_log_pdf, name='bank_log_pdf'),


    path('cash/', cash_index, name='cash_index'),
    path('cash/create/', cash_create, name='cash_create'),
    path('cash/update/<int:pk>/', cash_update, name='cash_update'),
    path('cash/delete/<int:pk>/', cash_delete, name='cash_delete'),

    path('available-amount/', available_amount,name='available_amount'),


    path('payments/', payment_index, name='payment_index'),
    path('payments/create/', payment_create, name='payment_create'),
    path('payments/update/<int:pk>/', payment_update, name='payment_update'),
    path('payments/delete/<int:pk>/', payment_delete, name='payment_delete'),


    path('expenses/', expense_index, name='expense_index'),
    path('expenses/pdf/', expense_pdf_export, name='expense_pdf_export'),
    path('expenses/create/', expense_create, name='expense_create'),
    path('expenses/update/<int:pk>/', expense_update, name='expense_update'),
    path('expenses/delete/<int:pk>/', expense_delete, name='expense_delete'),


    path('expense-categories/', expense_category_index, name='expense_category_index'),
    path('expense-categories/create/', expense_category_create, name='expense_category_create'),
    path('expense-categories/<int:pk>/update/', expense_category_update, name='expense_category_update'),
    path('expense-categories/<int:pk>/delete/', expense_category_delete, name='expense_category_delete'),


    path('workers/', worker_index, name='worker_index'),
    path('workers/create/', worker_create, name='worker_create'),
    path('workers/<int:pk>/update/', worker_update, name='worker_update'),
    path('workers/<int:pk>/delete/', worker_delete, name='worker_delete'),

    path('salary/', salary_index, name='salary_index'),
    path('salary/pdf/', salary_pdf, name='salary_pdf'),


    path('settings/', settings_view, name='settings'),
    path('settings/backup/', database_backup, name='database_backup'),




    path('password-change/',
        auth_views.PasswordChangeView.as_view(
            template_name='registration/password_change_form.html',
            success_url='/settings/'
        ),
        name='password_change'),
    path('help/', help, name='help'),

]
