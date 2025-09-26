# backend/voiceguard_project/urls.py

from django.contrib import admin
from django.urls import path
from call import views

# --- Add these two imports ---
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.lobby_view, name='lobby'),
    path('call/<str:call_id>/', views.call_view, name='call'),
]

# --- Add this line at the end ---
# This tells Django to serve static files when DEBUG is True
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()