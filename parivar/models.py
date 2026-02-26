from typing import Any
from django.db import models
from django.contrib.auth.models import AbstractUser, User
from django.db.models.signals import post_save
from django.dispatch import receiver
from parivar.constants import LANGUAGE_CHOICES
import boto3
from django.conf import settings

# from rest_framework.authtoken.models import TokenManager
from datetime import datetime
import os


class User(AbstractUser):
    mobile_number1 = models.CharField(max_length=15, blank=True, null=True)
    mobile_number2 = models.CharField(max_length=15, blank=True, null=True)

    class Meta:
        app_label = "parivar"


class Surname(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, blank=True)
    top_member = models.CharField(max_length=100, default="", blank=True)
    guj_name = models.CharField(max_length=255, blank=True, null=True)
    fix_order = models.CharField(max_length=10, null=True, blank=True)
    samaj = models.ForeignKey(
        "Samaj", on_delete=models.CASCADE, null=True, blank=True, related_name="surnames"
    )

    def __str__(self):
        if self.samaj:
            if self.samaj.village:
                v = self.samaj.village
                return f"{self.name} - {self.samaj.name} - {v.name} ({v.taluka.name} - {v.taluka.district.name})"
            return f"{self.name} - {self.samaj.name}"
        return f"{self.name} - No Samaj"

    class Meta:
        unique_together = ("name", "samaj")


class BloodGroup(models.Model):
    id = models.AutoField(primary_key=True)
    bloodgroup = models.CharField(max_length=10)

    def __str__(self):
        return self.bloodgroup


class State(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    guj_name = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name


class City(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    state = models.ForeignKey(State, related_name="state", on_delete=models.CASCADE)
    guj_name = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Cities"


class Country(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    guj_name = models.CharField(max_length=255, blank=True, null=True)
    flag = models.ImageField(upload_to="country_flags/", blank=True, null=True)

    def __str__(self):
        return self.name

#  new models 
class District(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    guj_name = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ("name",)
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["created_at"]),
        ]


class Taluka(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    guj_name = models.CharField(max_length=255, blank=True, null=True)
    district = models.ForeignKey(
        District, related_name="talukas", on_delete=models.CASCADE
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.district.name})"

    class Meta:
        unique_together = ("name", "district")
        indexes = [
            models.Index(fields=["district"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["created_at"]),
        ]


class Village(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    guj_name = models.CharField(max_length=255, blank=True, null=True)
    taluka = models.ForeignKey(Taluka, related_name="villages", on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.taluka.name} - {self.taluka.district.name})"

    class Meta:
        unique_together = ("name", "taluka")
        indexes = [
            models.Index(fields=["taluka"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["created_at"]),
        ]


class Samaj(models.Model):
    """Community/Samaj model representing surname-based communities"""

    CHOISE_PLAN = (
        ("free", "Free"),
        ("standard", "Standard")
    )

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, help_text="English samaj name")
    guj_name = models.CharField(max_length=255, blank=True, null=True, help_text="Gujarati samaj name")
    logo = models.ImageField(
        upload_to="samaj_logos/", blank=True, null=True, max_length=512
    )
    referral_code = models.CharField(max_length=50, blank=True, null=True, unique=True)
    is_premium = models.BooleanField(default=False)
    village = models.ForeignKey(
        Village, related_name="samaj_list", on_delete=models.CASCADE, null=True, blank=True
    )
    plan = models.CharField(choices=CHOISE_PLAN, default="free")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.village:
            return f"{self.name} - {self.village.name} ({self.village.taluka.name} - {self.village.taluka.district.name})"
        return f"{self.name} - No Village"

    class Meta:
        verbose_name_plural = "Samaj"
        unique_together = ("name", "village")

# new model added ended. 

class Person(models.Model):
    id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    surname = models.ForeignKey(
        Surname, on_delete=models.CASCADE, blank=True, null=True
    )
    date_of_birth = models.CharField(max_length=100, null=True, blank=True)
    mobile_number1 = models.CharField(max_length=12, blank=True, null=True)
    mobile_number2 = models.CharField(max_length=12, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    out_of_address = models.CharField(max_length=500, blank=True, null=True)
    out_of_mobile = models.CharField(max_length=100, blank=True, null=True)
    blood_group = models.CharField(max_length=10, blank=True, null=True)
    city = models.ForeignKey(City, on_delete=models.CASCADE, blank=True, null=True)
    state = models.ForeignKey(State, on_delete=models.CASCADE, blank=True, null=True)
    # new field added started. 
    # district = models.ForeignKey(
    #     District, on_delete=models.SET_NULL, blank=True, null=True
    # )
    # taluka = models.ForeignKey(Taluka, on_delete=models.SET_NULL, blank=True, null=True)
    # village = models.ForeignKey(
    #     Village, on_delete=models.SET_NULL, blank=True, null=True
    # )
    # new field added ended. 
    samaj = models.ForeignKey(
        Samaj, on_delete=models.SET_NULL, blank=True, null=True, related_name="members"
    )
    # is_premium = models.BooleanField(default=False)
    out_of_country = models.ForeignKey(Country, on_delete=models.CASCADE, default=1)
    is_out_of_country = models.BooleanField(default=False)
    international_mobile_number = models.CharField(max_length=50, blank=True, null=True)
    guj_first_name = models.CharField(max_length=100, blank=True, null=True)
    guj_middle_name = models.CharField(max_length=100, blank=True, null=True)
    child_flag = models.BooleanField(default=False)
    flag_show = models.BooleanField(default=False)
    is_demo = models.BooleanField(default=False, db_index=True)
    profile = models.ImageField(
        upload_to="profiles/", blank=True, null=True, max_length=512
    )
    thumb_profile = models.ImageField(
        upload_to="compress_img/", blank=True, null=True, max_length=512
    )
    status = models.CharField(max_length=50, blank=True, null=True)
    is_admin = models.BooleanField(default=False)
    is_same_as_father_address = models.BooleanField(default=False)
    is_same_as_son_address = models.BooleanField(default=False)
    # is_visible = models.BooleanField(default=False)
    is_super_admin = models.BooleanField(default=False)
    is_super_uper = models.BooleanField(default=False)
    is_show_old_contact = models.BooleanField(default=True)
    password = models.CharField(max_length=100, null=True, blank=True)
    platform = models.CharField(max_length=30, default="postman", null=True, blank=True)
    emoji = models.CharField(max_length=512, null=True, blank=True)
    is_registered_directly = models.BooleanField(default=False)
    update_field_message = models.CharField(max_length=1000, null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_by = models.IntegerField(blank=True, null=True, default=0)
    created_time = models.DateTimeField(auto_now_add=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return str(self.first_name)

    def get_surname_name(self, obj):
        return f"{obj.surname.name}"

    class Meta:
        unique_together = (
            "first_name",
            "middle_name",
            "date_of_birth",
            "surname",
            "mobile_number1",
            "mobile_number2",
        )
        indexes = [
            models.Index(fields=["samaj"]),
            models.Index(fields=["city"]),
            models.Index(fields=["state"]),
            models.Index(fields=["is_deleted"]),
            models.Index(fields=["created_time"]),
            models.Index(fields=["surname"]),
            models.Index(fields=["flag_show"]),
            models.Index(fields=["mobile_number1"]),
        ]

    def delete(self, *args, **kwargs):
        if self.profile and os.path.isfile(self.profile.path):
            os.remove(self.profile.path)
        if self.thumb_profile and os.path.isfile(self.thumb_profile.path):
            os.remove(self.thumb_profile.path)
        super(Person, self).delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        # Handle soft delete timestamp
        if self.is_deleted == True:
            self.deleted_at = datetime.now()
        else:
            self.deleted_at = None

        # Auto-assign default Patel samaj if no samaj is selected
        # if not self.samaj_id:   
            # try:
            #     # Get or create Patel samaj for THIS SPECIFIC village
            #     default_samaj, _ = Samaj.objects.get_or_create(
            #         name='Patel',
            #         # village=self.village,
            #         defaults={'guj_name': 'પટેલ', 'is_premium': False}
            #     )
            #     self.samaj = default_samaj
            # except Exception:
            #     pass  # If samaj assignment fails, continue without it

        # Auto-set is_premium based on samaj
        # if self.samaj:
        #     self.is_premium = self.samaj.is_premium
        # else:
        #     self.is_premium = False

        super(Person, self).save(*args, **kwargs)

# class Person(models.Model):
#     id = models.AutoField(primary_key=True)
#     first_name = models.CharField(max_length=100, blank=True, null=True)
#     middle_name = models.CharField(max_length=100, blank=True, null=True)
#     surname = models.ForeignKey(
#         Surname, on_delete=models.CASCADE, blank=True, null=True
#     )
#     date_of_birth = models.CharField(max_length=100, null=True, blank=True)
#     mobile_number1 = models.CharField(max_length=12, blank=True, null=True)
#     mobile_number2 = models.CharField(max_length=12, blank=True, null=True)
#     address = models.CharField(max_length=255, blank=True, null=True)
#     out_of_address = models.CharField(max_length=500, blank=True, null=True)
#     out_of_mobile = models.CharField(max_length=100, blank=True, null=True)
#     blood_group = models.CharField(max_length=10, blank=True, null=True)
#     city = models.ForeignKey(City, on_delete=models.CASCADE, blank=True, null=True)
#     state = models.ForeignKey(State, on_delete=models.CASCADE, blank=True, null=True)
#     out_of_country = models.ForeignKey(Country, on_delete=models.CASCADE, default=1)
#     child_flag = models.BooleanField(default=False)
#     flag_show = models.BooleanField(default=False)
#     profile = models.ImageField(
#         upload_to="profiles/", blank=True, null=True, max_length=512
#     )
#     thumb_profile = models.ImageField(
#         upload_to="compress_img/", blank=True, null=True, max_length=512
#     )
#     status = models.CharField(max_length=50, blank=True, null=True)
#     is_admin = models.BooleanField(default=False)
#     is_same_as_father_address = models.BooleanField(default=False)
#     is_same_as_son_address = models.BooleanField(default=False)
#     # is_visible = models.BooleanField(default=False)
#     is_super_admin = models.BooleanField(default=False)
#     is_super_uper = models.BooleanField(default=False)
#     is_show_old_contact = models.BooleanField(default=True)
#     password = models.CharField(max_length=100, null=True, blank=True)
#     platform = models.CharField(max_length=30, default="postman", null=True, blank=True)
#     emoji = models.CharField(max_length=512, null=True, blank=True)
#     is_registered_directly = models.BooleanField(default=False)
#     update_field_message = models.CharField(max_length=1000, null=True, blank=True)
#     is_deleted = models.BooleanField(default=False)
#     deleted_by = models.IntegerField(blank=True, null=True, default=0)
#     created_time = models.DateTimeField(auto_now_add=True, blank=True)
#     deleted_at = models.DateTimeField(null=True, blank=True)

#     def __str__(self) -> str:
#         return str(self.first_name)

#     def get_surname_name(self, obj):
#         return f"{obj.surname.name}"

#     class Meta:
#         unique_together = (
#             "first_name",
#             "middle_name",
#             "date_of_birth",
#             "surname",
#             "mobile_number1",
#             "mobile_number2",
#         )

#     def delete(self, *args, **kwargs):
#         if self.profile and os.path.isfile(self.profile.path):
#             os.remove(self.profile.path)
#         if self.thumb_profile and os.path.isfile(self.thumb_profile.path):
#             os.remove(self.thumb_profile.path)
#         super(Person, self).delete(*args, **kwargs)

#     def save(self, *args, **kwargs):
#         if self.is_deleted == True:
#             self.deleted_at = datetime.now()
#         else:
#             self.deleted_at = None
#         super(Person, self).save(*args, **kwargs)


class TranslatePerson(models.Model):
    person_id = models.ForeignKey(
        Person, on_delete=models.CASCADE, blank=True, null=True, related_name="translateperson"
    )
    first_name = models.CharField(max_length=500, blank=True, null=True)
    middle_name = models.CharField(max_length=500, blank=True, null=True)
    address = models.CharField(max_length=500, blank=True, null=True)
    out_of_address = models.CharField(max_length=500, blank=True, null=True)
    language = models.CharField(
        max_length=3,
        choices=LANGUAGE_CHOICES,
        default="public",
    )
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.first_name

    class Meta:
        unique_together = (
            "person_id",
            "first_name",
            "middle_name",
            "address",
            "language",
        )
        indexes = [
            models.Index(fields=["language"]),
            models.Index(fields=["is_deleted"]),
        ]


class ParentChildRelation(models.Model):
    parent = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="parent")
    child = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="child")
    created_user = models.ForeignKey(Person, on_delete=models.CASCADE)
    created = models.DateTimeField(
        auto_now_add=True,
        editable=False,
    )
    is_deleted = models.BooleanField(default=False)
    is_demo = models.BooleanField(default=False, db_index=True)
    modified = models.DateTimeField(
        auto_now=True,
        null=True,
        editable=False,
    )

    def __str__(self):
        return str(self.id)

    class Meta:
        indexes = [
            models.Index(fields=["parent"]),
            models.Index(fields=["child"]),
            models.Index(fields=["is_deleted"]),
            models.Index(fields=["created"]),
        ]


class AdsSetting(models.Model):
    app_title = models.CharField(max_length=200)
    samaj = models.ManyToManyField(
        "Samaj", blank=True, related_name="ads_settings"
    )
    ads_setting = models.JSONField()
    commit_no = models.CharField(max_length=200, default="0000")

    def __str__(self):
        return self.app_title

    class Meta:
        verbose_name = "ads setting"
        verbose_name_plural = "ads setting"


class Banner(models.Model):
    id = models.AutoField(primary_key=True)
    redirect_url = models.CharField(max_length=255, blank=True, null=True)
    images = models.ImageField(upload_to="banner_images/")
    created_date = models.DateTimeField(auto_now_add=True)
    created_person = models.ForeignKey(Person, on_delete=models.CASCADE)
    expire_date = models.DateField(blank=True, null=True)
    is_ad_lable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.pk:
            old_image = Banner.objects.get(pk=self.pk).images
            if old_image and old_image != self.images:
                if os.path.isfile(old_image.path):
                    os.remove(old_image.path)
        super(Banner, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.images:
            if os.path.isfile(self.images.path):
                os.remove(self.images.path)
        super(Banner, self).delete(*args, **kwargs)


class RandomBanner(models.Model):
    is_random_banner = models.BooleanField(default=False)
    samaj = models.ForeignKey(
        "Samaj", on_delete=models.CASCADE, null=True, blank=True, related_name="random_banners"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)


class PersonUpdateLog(models.Model):
    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="update_logs"
    )
    updated_history = models.CharField(max_length=1000, null=True, blank=True)
    created_person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="created_updates"
    )
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
 