from django.contrib import admin
from .models import (
    Company,
    Client,
    Bank,
    BankTransfer,
    Payment,
    Worker,
    WorkerName,
    ExpenseCategory,
    ExpenseSubCategory,
    Expense,
    ActivityLog,
    AppSettings,
    BackupHistory
)


# =====================================================
# COMPANY ADMIN
# =====================================================

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'name',
        'is_active',
    )

    search_fields = (
        'name',
    )

    list_filter = (
        'is_active',
    )

    ordering = (
        '-id',
    )


# =====================================================
# CLIENT ADMIN
# =====================================================

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'name',
        'location',
        'budget',
        'company',
        'is_active',
    )

    search_fields = (
        'name',
        'location',
    )

    list_filter = (
        'company',
        'is_active',
    )

    ordering = (
        '-id',
    )


# =====================================================
# BANK ADMIN
# =====================================================

@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'name',
        'company',
        'opening_balance',
        'available_balance',
        'is_active',
    )

    search_fields = (
        'name',
    )

    list_filter = (
        'company',
        'is_active',
    )

    ordering = (
        '-id',
    )


# =====================================================
# BANK TRANSFER ADMIN
# =====================================================

@admin.register(BankTransfer)
class BankTransferAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'from_bank',
        'to_bank',
        'amount',
        'transfer_date',
    )

    search_fields = (
        'from_bank__name',
        'to_bank__name',
    )

    list_filter = (
        'transfer_date',
    )

    ordering = (
        '-id',
    )


# =====================================================
# PAYMENT ADMIN
# =====================================================

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'client',
        'bank',
        'amount',
        'payment_mode',
        'payment_date',
    )

    search_fields = (
        'client__name',
        'bank__name',
    )

    list_filter = (
        'payment_mode',
        'payment_date',
    )

    ordering = (
        '-id',
    )


# =====================================================
# WORKER ADMIN
# =====================================================

@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'name',
        'company',
        'is_active',
    )

    search_fields = (
        'name',
    )

    list_filter = (
        'company',
        'is_active',
    )

    ordering = (
        '-id',
    )


# =====================================================
# WORKER NAME ADMIN
# =====================================================

@admin.register(WorkerName)
class WorkerNameAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'name',
        'worker',
        'is_active',
    )

    search_fields = (
        'name',
        'worker__name',
    )

    list_filter = (
        'worker',
        'is_active',
    )

    ordering = (
        '-id',
    )


# =====================================================
# EXPENSE CATEGORY ADMIN
# =====================================================

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'name',
        'company',
    )

    search_fields = (
        'name',
    )

    list_filter = (
        'company',
    )

    ordering = (
        '-id',
    )


# =====================================================
# EXPENSE SUB CATEGORY ADMIN
# =====================================================

@admin.register(ExpenseSubCategory)
class ExpenseSubCategoryAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'name',
        'category',
    )

    search_fields = (
        'name',
        'category__name',
    )

    list_filter = (
        'category',
    )

    ordering = (
        '-id',
    )


# =====================================================
# EXPENSE ADMIN
# =====================================================

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'client',
        'category',
        'subcategory',
        'amount',
        'spend_mode',
        'expense_date',
    )

    search_fields = (
        'client__name',
        'description',
        'category__name',
    )

    list_filter = (
        'spend_mode',
        'expense_date',
        'category',
    )

    ordering = (
        '-id',
    )


# =====================================================
# ACTIVITY LOG ADMIN
# =====================================================

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'action',
        'created_at',
    )

    search_fields = (
        'action',
        'description',
    )

    list_filter = (
        'created_at',
    )

    ordering = (
        '-created_at',
    )

    readonly_fields = (
        'created_at',
    )


# =====================================================
# APP SETTINGS ADMIN
# =====================================================

@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):

    list_display = (
        'notification_email',
        'favicon',
    )


# =====================================================
# BACKUP HISTORY ADMIN
# =====================================================

@admin.register(BackupHistory)
class BackupHistoryAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'file_name',
        'file_size_mb',
        'created_by',
        'created_at',
    )

    search_fields = (
        'file_name',
    )

    list_filter = (
        'created_at',
    )

    ordering = (
        '-created_at',
    )

    readonly_fields = (
        'created_at',
    )