from django.urls import re_path

from puzzles.messaging import TeamNotificationsConsumer, HintsConsumer

websocket_urlpatterns = [
    re_path('^ws/team$', TeamNotificationsConsumer.as_asgi()),
    re_path('^ws/hints$', HintsConsumer.as_asgi()),
]
