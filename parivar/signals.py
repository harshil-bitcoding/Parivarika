from django.db.models.signals import post_save
from django.dispatch import receiver

from parivar.serializers import PersonSerializer, TranslatePersonSerializer
from .models import Person, Surname


@receiver(post_save, sender=Surname)
def surname_save(sender, created, instance, **kwargs):
    if created:
        person_data = {
            "first_name": instance.name,
            "middle_name": instance.name,
            "address": "",
            "blood_group": 1,
            "date_of_birth": "1800-01-01 00:00:00.000",
            "out_of_country": 1,
            "out_of_address": "",
            "city": 1,
            "state": 1,
            "mobile_number1": "",
            "mobile_number2": "",
            "surname": instance.id,
            "flag_show": True,
            "is_admin": False,
            "is_registered_directly": True,
        }

        # Check if the person already exists with the unique constraint
        existing_person = Person.objects.filter(
            first_name=instance.name,
            middle_name=instance.name,
            date_of_birth="1800-01-01 00:00:00.000",
            surname=instance.id,
            mobile_number1="",
            mobile_number2="",
        ).first()

        if existing_person:
            person_instance = existing_person

        else:
            # Serialize and save Person
            person_serializer = PersonSerializer(data=person_data)
            if person_serializer.is_valid():
                person_instance = person_serializer.save()
                instance.top_member = person_instance.id
                instance.save()

        if instance.guj_name:
            # Prepare translation data
            person_translate_data = {
                "first_name": instance.guj_name,
                "person_id": person_instance.id,
                "middle_name": instance.guj_name,
                "address": "",
                "out_of_address": "",
                "language": "guj",
            }
            person_translate_serializer = TranslatePersonSerializer(
                data=person_translate_data
            )
            try:
                if person_translate_serializer.is_valid():
                    person_translate_instance = person_translate_serializer.save()

            except Exception as e:
                pass
