from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext as _

class CustomUserManager(BaseUserManager):
    """
    Custom user model manager where mobile numbers are the unique identifiers
    for authentication instead of usernames.
    """

    def create_user(self, mobile_number1, mobile_number2, password, **extra_fields):
        if not mobile_number1:
            raise ValueError(_('Users must have a mobile number'))
        user = self.model(mobile_number1=mobile_number1, mobile_number2=mobile_number2, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, mobile_number1, mobile_number2, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(mobile_number1, mobile_number2, password, **extra_fields)

