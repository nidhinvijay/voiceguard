# core/urls.py
from django.urls import path,re_path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('token/', views.get_twilio_token, name='get_twilio_token'),

    # Directory & Contacts
    path('directory/', views.directory_page, name='directory_page'),
    path('directory/search', views.directory_search, name='directory_search'),
    path('contacts/request', views.contacts_request, name='contacts_request'),
    path('contacts/accept', views.contacts_accept, name='contacts_accept'),
    path('contacts/block', views.contacts_block, name='contacts_block'),
    path('contacts/pending', views.contacts_pending, name='contacts_pending'),
    path('contacts/list', views.contacts_list, name='contacts_list'),

    # Calls (already added in Set 5)
    re_path(r'^calls/finish/?$', views.calls_finish, name='calls_finish'),
    path('calls/history', views.calls_history, name='calls_history'),
    path('users/lifetime_avg', views.lifetime_avg, name='lifetime_avg'),

    # NEW: history page (HTML)
    path('history/', views.history_page, name='history_page'),
    path('twiml/voice', views.twiml_voice, name='twiml_voice'),  # NEW
]
