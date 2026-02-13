# accountsApp/middleware.py
import time
from django.shortcuts import redirect
from django.urls import resolve
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import logout



# accountsApp/middleware.py
import time
from django.shortcuts import redirect
from django.urls import resolve
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import logout

class SessionTimeoutMiddleware(MiddlewareMixin):

    PUBLIC_NAMES = {'login', 'logout', 'password_change', 'switch_company'}
    PUBLIC_PATHS = ('/static/', '/media/', '/admin/')
    TIMEOUT = 15 * 60

    def process_request(self, request):

        path = request.path

        if path.startswith(self.PUBLIC_PATHS):
            return None

        try:
            url_name = resolve(path).url_name
        except:
            url_name = None

        # 🚫 NOT LOGGED IN
        if not request.user.is_authenticated:
            if url_name in self.PUBLIC_NAMES:
                return None

            request.session['last_page'] = request.get_full_path()
            return redirect('login')

        # ⏳ SESSION TIMEOUT
        now = int(time.time())
        last_activity = request.session.get('last_activity')

        if last_activity and now - last_activity > self.TIMEOUT:
            logout(request)
            request.session['session_expired'] = True
            return redirect('login')

        request.session['last_activity'] = now

        # ✅ SAVE LAST PAGE (ONLY REAL PAGES)
        if url_name not in self.PUBLIC_NAMES:
            request.session['last_page'] = request.get_full_path()

        return None



class LastPageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "GET":
            request.session['last_page'] = request.get_full_path()
        return self.get_response(request)


