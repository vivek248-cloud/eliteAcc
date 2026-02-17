
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import handler404, handler500, handler403, handler400
from accountsApp import views


urlpatterns = [

    path('', include('accountsApp.urls')),
    path('admin/', admin.site.urls),
    
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


from django.views.generic import RedirectView

urlpatterns += [
    path('favicon.ico', RedirectView.as_view(
        url='/static/favicon.ico', permanent=True)),
]




handler404 = 'accountsApp.views.error_404'
handler500 = 'accountsApp.views.error_500'
handler403 = 'accountsApp.views.error_403'
handler400 = 'accountsApp.views.error_400'
