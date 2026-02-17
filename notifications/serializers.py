from rest_framework import serializers
from notifications.models import Notification, NotificationImage


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "sub_title", "expire_date"]


class NotificationCreateSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "sub_title",
            "redirect_url",
            "image_url",
            "is_event",
            "event_reminder_date",
            "filter",
            "to_person",
            "created_user",
            "start_date",
            "expire_date",
            "is_show_left_time",
            "is_show_ad_lable",
        ]

    def get_image_url(self, obj):
        images = NotificationImage.objects.filter(notification_id=obj.id)
        return [image.image_url.url for image in images if image.image_url]


class NotificationNewGetSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    start_date = serializers.SerializerMethodField()
    expire_date = serializers.SerializerMethodField()
    event_reminder_date = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "sub_title",
            "redirect_url",
            "image_url",
            "is_event",
            "event_reminder_date",
            "filter",
            "created_user",
            "start_date",
            "expire_date",
            "is_show_left_time",
            "is_show_ad_lable",
        ]

    def get_image_url(self, obj):
        images = NotificationImage.objects.filter(notification_id=obj.id)
        return [image.image_url.url for image in images if image.image_url]

    def get_start_date(self, obj):
        # Convert datetime to milliseconds timestamp
        if obj.start_date:
            return int(obj.start_date.timestamp() * 1000)
        return None

    def get_expire_date(self, obj):
        # Convert datetime to milliseconds timestamp
        if obj.expire_date:
            return int(obj.expire_date.timestamp() * 1000)
        return None

    def get_event_reminder_date(self, obj):
        # Convert datetime to milliseconds timestamp
        if obj.event_reminder_date:
            return int(obj.event_reminder_date.timestamp() * 1000)
        return None
