# backend/call/views.py

from django.shortcuts import render

def lobby_view(request):
    """Renders the lobby page."""
    return render(request, 'lobby.html')

def call_view(request, call_id):
    """Renders the call page."""
    context = {'call_id': call_id}
    return render(request, 'call.html', context)