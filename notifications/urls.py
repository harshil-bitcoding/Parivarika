from django.urls import path
from . import views

app_name = "notificartions"

urlpatterns = [
    path("api/v4/player-id", views.CreatePlayerId.as_view(), name="player_id"),
    path(
        "api/v4/notification",
        views.NotificationDetailView.as_view(),
        name="notification_detail",
    ),
    path(
        "api/v4/notification/<int:pk>",
        views.NotificationDetailView.as_view(),
        name="notification_detail",
    ),
    path(
        "api/v4/pending-notification-send",
        views.PendingNotificationSend.as_view(),
        name="pending_notification_send",
    ),
    path(
        "api/v4/remove-notification",
        views.NotificationDeleteView.as_view(),
        name="remove_notification",
    ),
    # Birthday API (standalone GET endpoint)
    path(
        "api/v4/birthdays",
        views.BirthdayAPIView.as_view(),
        name="birthday_list",
    ),
    # Birthday Cron Send API (triggered daily at 12:00 AM by system cron)
    path(
        "api/v4/send-birthday-notifications",
        views.BirthdaySendView.as_view(),
        name="birthday_send",
    ),
]
