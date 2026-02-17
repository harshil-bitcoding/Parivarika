from storages.backends.s3boto3 import S3Boto3Storage


class NotificationImageS3Storage(S3Boto3Storage):
    location = "Billaparivar"
    bucket_name = "classdekho"
    custom_domain = "classdekho.s3.ap-south-1.amazonaws.com"
