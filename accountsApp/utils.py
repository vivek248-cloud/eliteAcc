from functools import wraps
from django.shortcuts import redirect

def require_company(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('selected_company_id'):
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
