import time
from django.shortcuts import redirect
from django.urls import resolve
from django.contrib import messages
from django.utils.deprecation import MiddlewareMixin


class SessionTimeoutMiddleware(MiddlewareMixin):

    PUBLIC_NAMES = {
        'login',
        'logout',
        'password_change',
    }

    PUBLIC_PATHS = (
        '/static/',
        '/media/',
        '/admin/',
    )

    TIMEOUT = 15 * 60   # 15 minutes

    def process_request(self, request):

        path = request.path

        # ✅ Always allow static/media/admin
        if path.startswith(self.PUBLIC_PATHS):
            return None

        # Safely resolve url name
        try:
            url_name = resolve(path).url_name
        except:
            url_name = None

        # ============================
        # 🚫 NOT LOGGED IN
        # ============================
        if not request.user.is_authenticated:

            # Allow login + public routes
            if url_name in self.PUBLIC_NAMES:
                return None

            # Save intended page
            request.session['last_page'] = request.get_full_path()

            return redirect('login')

        # ============================
        # ⏳ SESSION TIMEOUT
        # ============================
        now = int(time.time())
        last_activity = request.session.get('last_activity')

        if last_activity and now - last_activity > self.TIMEOUT:
            from django.contrib.auth import logout
            logout(request)

            messages.warning(request, "Session expired due to inactivity")

            return redirect('login')

        request.session['last_activity'] = now

        # ============================
        # 📌 SAVE LAST PAGE (real pages only)
        # ============================
        if url_name not in self.PUBLIC_NAMES:
            request.session['last_page'] = request.get_full_path()

        return None
