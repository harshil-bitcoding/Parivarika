from django.db import models
from parivar.models import Person
from notifications.storages import NotificationImageS3Storage


class PersonPlayerId(models.Model):
    PLATFORM_CHOICE = [("Android", "Android"), ("Ios", "Ios")]
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    player_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    platform = models.CharField(
        max_length=100,
        choices=PLATFORM_CHOICE,
        default="Android",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Notification(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    sub_title = models.CharField(max_length=255, blank=True, null=True)
    redirect_url = models.CharField(max_length=255, blank=True, null=True)
    start_date = models.DateTimeField(blank=True, null=True)
    expire_date = models.DateTimeField(blank=False, null=False)
    is_event = models.BooleanField(default=False)
    to_person = models.ManyToManyField(
        Person, related_name="notifications_persons", blank=True
    )
    event_reminder_date = models.DateTimeField(blank=True, null=True)
    created_user = models.CharField(max_length=255, blank=True, null=True)
    filter = models.JSONField(null=True, blank=True)
    is_show_left_time = models.BooleanField(default=False)
    is_show_ad_lable = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class NotificationImage(models.Model):
    notification_id = models.ForeignKey(Notification, on_delete=models.CASCADE)
    image_url = models.FileField(
        storage=NotificationImageS3Storage(),
        upload_to="notification_images/",
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.notification_id.title

    def delete(self, *args, **kwargs):
        # Delete the file from S3
        self.image_url.delete(save=False)
        super().delete(*args, **kwargs)
