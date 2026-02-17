from django.contrib import admin

from notifications.models import Notification, NotificationImage, PersonPlayerId


# Register your models here.
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "title",
        "is_event",
        "start_date",
        "expire_date",
        "created_user",
        "is_show_left_time",
        "created_at",
    ]
    search_fields = [
        "id",
        "title",
        "is_show_left_time",
        "created_user__first_name",
        "created_user__id",
    ]


@admin.register(NotificationImage)
class NotificationImageAdmin(admin.ModelAdmin):
    list_display = ["id", "notification_id", "image_url"]


@admin.register(PersonPlayerId)
class UserPlayerIdAdmin(admin.ModelAdmin):
    list_display = ["id", "person", "player_id", "platform", "created_at", "updated_at"]
    search_fields = [
        "id",
        "player_id",
        "person__first_name",
        "person__id",
        "person__surname__name",
    ]
