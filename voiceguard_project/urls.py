from django.contrib import admin
from django.urls import path, include
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.generic import RedirectView
from django.templatetags.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    # Serve /favicon.ico from /static/favicon.ico
    path('favicon.ico', RedirectView.as_view(
        url=static('favicon.ico'), permanent=False
    )),
]

urlpatterns += staticfiles_urlpatterns()
