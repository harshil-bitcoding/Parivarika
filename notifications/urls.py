from django.urls import path
from . import views

app_name = "notificartions"

urlpatterns = [
    path("api/v3/player-id", views.CreatePlayerId.as_view(), name="player_id"),
    path(
        "api/v3/notification",
        views.NotificationDetailView.as_view(),
        name="notification_detail",
    ),
    path(
        "api/v3/notification/<int:pk>",
        views.NotificationDetailView.as_view(),
        name="notification_detail",
    ),
    path(
        "api/v3/pending-notification-send",
        views.PendingNotificationSend.as_view(),
        name="pending_notification_send",
    ),
    path(
        "api/v3/remove-notification",
        views.NotificationDeleteView.as_view(),
        name="remove_notification",
    ),
]
