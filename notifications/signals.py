from django.dispatch import receiver
from django.db.models.signals import pre_delete

from notifications.models import NotificationImage


@receiver(pre_delete, sender=NotificationImage)
def delete_file_from_s3(sender, instance, **kwargs):
    
    # This will delete the file from S3 before the model instance is deleted
    if instance.image_url:
        instance.image_url.delete(save=False)
