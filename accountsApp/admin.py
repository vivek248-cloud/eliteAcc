from django.contrib import admin

# Register your models here.
from .models import *

admin.site.register(Client)
admin.site.register(Company)
admin.site.register(Payment)
admin.site.register(Expense)
admin.site.register(Bank)

admin.site.register(Worker)

admin.site.register(ExpenseCategory)

admin.site.register(AppSettings)
admin.site.register(BackupHistory)