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


# ---------------------------------------------------------------------------
# Birthday serializer
# ---------------------------------------------------------------------------

class BirthdayPersonSerializer(serializers.Serializer):
    """
    Read-only serializer for birthday list items.
    Maps Person fields to the agreed-upon birthday response shape.
    """
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    middle_name = serializers.CharField(allow_null=True, allow_blank=True)
    last_name = serializers.SerializerMethodField()
    birth_date = serializers.SerializerMethodField()
    samaj = serializers.SerializerMethodField()
    flag_show = serializers.BooleanField()
    profile = serializers.SerializerMethodField()
    thumb_profile = serializers.SerializerMethodField()

    def get_last_name(self, obj):
        """Returns the English surname name."""
        if obj.surname:
            return obj.surname.name
        return ""

    def get_birth_date(self, obj):
        """Returns only the date portion (YYYY-MM-DD) of date_of_birth."""
        dob = (obj.date_of_birth or "").strip()
        if dob and len(dob) >= 10:
            return dob[:10]  # YYYY-MM-DD
        return dob or None

    def get_samaj(self, obj):
        """Returns samaj name."""
        if obj.samaj:
            return obj.samaj.name
        return None

    def get_profile(self, obj):
        import os
        request = self.context.get('request')
        if obj.profile:
            try:
                url = obj.profile.url
                return request.build_absolute_uri(url) if request else url
            except Exception:
                pass
        fallback = os.getenv("DEFAULT_PROFILE_PATH", "")
        return request.build_absolute_uri(fallback) if request and fallback else fallback

    def get_thumb_profile(self, obj):
        import os
        request = self.context.get('request')
        if obj.thumb_profile:
            try:
                url = obj.thumb_profile.url
                return request.build_absolute_uri(url) if request else url
            except Exception:
                pass
        fallback = os.getenv("DEFAULT_PROFILE_PATH", "")
        return request.build_absolute_uri(fallback) if request and fallback else fallback
