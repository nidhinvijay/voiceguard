# core/routing.py

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # This regex captures a word for the room name and passes it to the consumer
    re_path(r'ws/call/(?P<room_name>\w+)/$', consumers.CallConsumer.as_asgi()),
]