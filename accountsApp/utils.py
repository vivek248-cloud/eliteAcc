from functools import wraps
from django.shortcuts import redirect

def require_company(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('selected_company_id'):
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


import os
import zipfile
import subprocess
from datetime import timedelta
from django.conf import settings
from django.utils.timezone import now
from django.core.mail import send_mail
from .models import BackupHistory, AppSettings


def create_database_backup(user=None):
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

    with open(sql_file, "w") as f:
        subprocess.run(dump_command, stdout=f, check=True)

    with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(sql_file, arcname=os.path.basename(sql_file))

    os.remove(sql_file)

    file_size_mb = round(os.path.getsize(zip_file) / (1024 * 1024), 2)

    BackupHistory.objects.create(
        file_name=os.path.basename(zip_file),
        file_path=zip_file,
        file_size_mb=file_size_mb,
        created_by=user
    )

    # Auto delete > 30 days
    cutoff = now() - timedelta(days=30)
    old_backups = BackupHistory.objects.filter(created_at__lt=cutoff)

    for backup in old_backups:
        if os.path.exists(backup.file_path):
            os.remove(backup.file_path)
        backup.delete()

    # Send email
    settings_obj = AppSettings.objects.first()

    if settings_obj and settings_obj.notification_email:
        send_mail(
            "Elite Accounts - Auto Backup Completed",
            f"""
Backup created successfully.

File: {os.path.basename(zip_file)}
Size: {file_size_mb} MB
Time: {now_dt.strftime('%d-%m-%Y %H:%M')}

Location:
{zip_file}
""",
            settings.DEFAULT_FROM_EMAIL,
            [settings_obj.notification_email],
            fail_silently=False
        )

    return zip_file
