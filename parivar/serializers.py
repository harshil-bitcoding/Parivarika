from rest_framework import serializers
from .models import *
from django.db.models import Q
from django.core.exceptions import ValidationError
import re
import ast
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "mobile_number1", "mobile_number2"]

class SurnameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Surname
        fields = ["id", "name", "top_member", "guj_name"]

class GetSurnameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Surname
        fields = ["id", "name", "top_member"]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        lang = self.context.get("lang", "en")
        if lang == "guj":
            representation["name"] = (
                instance.guj_name if instance.guj_name else instance.name
            )
        else:
            representation["name"] = instance.name
        return representation

class BloodGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = BloodGroup
        fields = ["id", "bloodgroup"]

# new serializer added started. 
class DistrictSerializer(serializers.ModelSerializer):

    class Meta:
        model = District
        fields = ["id", "name", "guj_name"]

    def to_representation(self, instance):
        lang = self.context.get("lang", "en")
        data = super().to_representation(instance)
        if lang == "guj" and instance.guj_name:
            data["name"] = instance.guj_name
        return data


class TalukaSerializer(serializers.ModelSerializer):
    district_name = serializers.ReadOnlyField(source="district.name")

    class Meta:
        model = Taluka
        fields = ["id", "name", "guj_name", "district", "district_name"]

    def to_representation(self, instance):
        lang = self.context.get("lang", "en")
        data = super().to_representation(instance)
        if lang == "guj" and instance.guj_name:
            data["name"] = instance.guj_name
        return data

class VillageSerializer(serializers.ModelSerializer):
    taluka_name = serializers.ReadOnlyField(source="taluka.name")
    # samaj_list = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Village
        fields = ["id", "name", "guj_name", "taluka", "taluka_name"]

    # def get_samaj_list(self, obj):
    #     from .models import Samaj
    #     lang = self.context.get("lang", "en")
    #     samaj_queryset = obj.samaj_list.all()
    #     return SamajSerializer(samaj_queryset, many=True, context={"lang": lang}).data

    def to_representation(self, instance):
        lang = self.context.get("lang", "en")
        data = super().to_representation(instance)
        if lang == "guj" and instance.guj_name:
            data["name"] = instance.guj_name
        return data


class SamajSerializer(serializers.ModelSerializer):
    """Serializer for Samaj (community) model"""
    village_name = serializers.SerializerMethodField(read_only=True)
    taluka_name = serializers.SerializerMethodField(read_only=True)
    district_name = serializers.SerializerMethodField(read_only=True)
    taluka = serializers.SerializerMethodField(read_only=True)
    district = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Samaj
        fields = [
            'id', 'name', 'guj_name', 'logo', 'referral_code', 'is_premium', 'plan', 
            'village_name', 'taluka', 'taluka_name', 'district', 'district_name'
        ]
    
    def get_village_name(self, obj):
        lang = self.context.get("lang", "en")
        if obj.village:
            if lang == "guj" and obj.village.guj_name:
                return obj.village.guj_name
            return obj.village.name
        return None

    def get_taluka_name(self, obj):
        lang = self.context.get("lang", "en")
        if obj.village and obj.village.taluka:
            if lang == "guj" and obj.village.taluka.guj_name:
                return obj.village.taluka.guj_name
            return obj.village.taluka.name
        return None

    def get_district_name(self, obj):
        lang = self.context.get("lang", "en")
        if obj.village and obj.village.taluka and obj.village.taluka.district:
            if lang == "guj" and obj.village.taluka.district.guj_name:
                return obj.village.taluka.district.guj_name
            return obj.village.taluka.district.name
        return None

    def get_village(self, obj):
        return self.get_village_name(obj) or ""

    def get_taluka(self, obj):
        return self.get_taluka_name(obj) or ""

    def get_district(self, obj):
        return self.get_district_name(obj) or ""

    def to_representation(self, instance):
        data = super().to_representation(instance)
        lang = self.context.get('lang', 'en')
        if lang == 'guj' and instance.guj_name:
            data['name'] = instance.guj_name
        return data



class PersonV4Serializer(serializers.ModelSerializer):
    surname = serializers.SerializerMethodField(source='surname.name', read_only=True)
    village_name = serializers.SerializerMethodField(source='samaj.village.name', read_only=True)
    taluka_name = serializers.SerializerMethodField()
    district_name = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField(source='city.name', read_only=True)
    state = serializers.SerializerMethodField(source='state.name', read_only=True)
    out_of_country = serializers.SerializerMethodField(source='out_of_country.name', read_only=True)
    # relations = serializers.SerializerMethodField()
    village_id = serializers.IntegerField(source='samaj.village_id', read_only=True)
    samaj_id = serializers.IntegerField(source='samaj.id', read_only=True)
    referal_code = serializers.CharField(source='samaj.referral_code', read_only=True)
    is_premium = serializers.BooleanField(source='samaj.is_premium', read_only=True)
    plan = serializers.CharField(source='samaj.plan', read_only=True)
    trans_first_name = serializers.SerializerMethodField(read_only=True, required=False)
    trans_middle_name = serializers.SerializerMethodField(read_only=True, required=False)

    class Meta:
        model = Person
        fields = [
            "id",
            "first_name",
            "middle_name",
            "surname",
            "mobile_number1",
            "mobile_number2",
            "address",
            "is_same_as_father_address",
            "is_same_as_son_address",
            "out_of_address",
            "date_of_birth",
            "blood_group",
            "city",
            "state",
            "out_of_country",
            "out_of_mobile",
            "district_name",
            "taluka_name",
            "village_id",
            "village_name",
            "profile",
            "thumb_profile",
            "status",
            "flag_show",
            "is_admin",
            "is_super_admin",
            "is_registered_directly",
            "update_field_message",
            "platform",
            # "relations",
            "is_super_uper",
            "referal_code",
            "is_premium",
            "plan",
            "is_show_old_contact",
            "password",
            "is_deleted",
            "deleted_by",
            "samaj_id",
            "referal_code",
            "is_premium",
            "trans_first_name",
            "trans_middle_name",
            "is_demo",
        ]

    def get_surname(self, obj):
        lang = self.context.get("lang", "en")
        if obj.surname:
            if lang == "guj" and obj.surname.guj_name:
                return obj.surname.guj_name
            return obj.surname.name
        return None

    def get_village_name(self, obj):
        lang = self.context.get("lang", "en")
        if obj.samaj and obj.samaj.village:
            if lang == "guj" and obj.samaj.village.guj_name:
                return obj.samaj.village.guj_name
            return obj.samaj.village.name
        return None

    def get_taluka_name(self, obj):
        lang = self.context.get("lang", "en")
        if obj.samaj and obj.samaj.village and obj.samaj.village.taluka:
            if lang == "guj" and obj.samaj.village.taluka.guj_name:
                return obj.samaj.village.taluka.guj_name
            return obj.samaj.village.taluka.name
        return None

    def get_district_name(self, obj):
        lang = self.context.get("lang", "en")
        if obj.samaj and obj.samaj.village and obj.samaj.village.taluka and obj.samaj.village.taluka.district:
            if lang == "guj" and obj.samaj.village.taluka.district.guj_name:
                return obj.samaj.village.taluka.district.guj_name
            return obj.samaj.village.taluka.district.name
        return None

    def get_city(self, obj):
        lang = self.context.get("lang", "en")
        if obj.city:
            if lang == "guj" and obj.city.guj_name:
                return obj.city.guj_name
            return obj.city.name
        return None

    def get_state(self, obj):
        lang = self.context.get("lang", "en")
        if obj.state:
            if lang == "guj" and obj.state.guj_name:
                return obj.state.guj_name
            return obj.state.name
        return None

    def get_out_of_country(self, obj):
        lang = self.context.get("lang", "en")
        if obj.out_of_country:
            if lang == "guj" and obj.out_of_country.guj_name:
                return obj.out_of_country.guj_name
            return obj.out_of_country.name
        return ""

    def get_trans_first_name(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        if translate_data and translate_data.first_name:
            return translate_data.first_name
        return obj.guj_first_name if hasattr(obj, 'guj_first_name') and obj.guj_first_name else obj.first_name

    def get_trans_middle_name(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        if translate_data and translate_data.middle_name:
            return translate_data.middle_name
        return obj.guj_middle_name if hasattr(obj, 'guj_middle_name') and obj.guj_middle_name else obj.middle_name

    def get_relations(self, obj):
        # is_demo = self.context.get("is_demo", False)
        # if is_demo:
        #     rel_model = DemoParentChildRelation
        #     # If obj is a real Person, we need the DemoPerson counterpart for relations
        #     if isinstance(obj, Person):
        #         obj = DemoPerson.objects.filter(
        #             Q(mobile_number1=obj.mobile_number1) | Q(mobile_number2=obj.mobile_number1)
        #         ).first()
        #         if not obj:
        #             return []
        # else:
        rel_model = ParentChildRelation

        # Fetch relations where the person is either parent or child
        relations = rel_model.objects.filter(
            Q(parent=obj) | Q(child=obj)
        )
        if hasattr(rel_model, 'is_deleted'):
            relations = relations.filter(is_deleted=False)

        return [
            {"id": r.id, "parent": r.parent.id, "child": r.child.id}
            for r in relations
        ]

    def validate(self, data):

        import re
        from django.db.models import Q
        from datetime import datetime
        from .models import Person

        # ---------- REQUIRED FIELDS ----------
        if not data.get("first_name"):
            raise serializers.ValidationError({"message": "First name is required."})

        if not data.get("middle_name"):
            raise serializers.ValidationError({"message": "Middle name is required."})

        flag_show = data.get("flag_show")
        if flag_show is not None and not isinstance(flag_show, bool):
            raise serializers.ValidationError({"message": "Flag show must be boolean."})

        # ---------- MOBILE VALIDATION ----------
        mobile_number1 = (data.get("mobile_number1") or "").strip()
        mobile_number2 = (data.get("mobile_number2") or "").strip()

        mobile_numbers = [m for m in [mobile_number1, mobile_number2] if m]

        # allow empty mobiles
        if mobile_numbers:

            # format validation
            for num in mobile_numbers:
                if not re.match(r"^\d{7,14}$", num):
                    raise serializers.ValidationError({
                        "message": "Mobile number must be 7-14 digits only."
                    })

            # same number check
            if len(mobile_numbers) == 2 and mobile_number1 == mobile_number2:
                raise serializers.ValidationError({
                    "message": "Mobile number 1 and 2 cannot be same."
                })

            # uniqueness check
            person_id = self.instance.id if self.instance else None

            query = Q()
            for num in mobile_numbers:
                query |= Q(mobile_number1=num) | Q(mobile_number2=num)

            existing = Person.objects.filter(query, is_deleted=False)

            if person_id:
                existing = existing.exclude(id=person_id)

            if existing.exists():
                raise serializers.ValidationError({
                    "message": "Mobile number already registered."
                })

        # ---------- DATE VALIDATION ----------
        date_of_birth_str = data.get("date_of_birth")
        if date_of_birth_str:
            parsed_date = None
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    parsed_date = datetime.strptime(date_of_birth_str, fmt)
                    break
                except ValueError:
                    continue
            if parsed_date is None:
                raise serializers.ValidationError({
                    "message": "Invalid date format. Expected YYYY-MM-DD or YYYY-MM-DD HH:MM:SS"
                })
            # Normalize: always store as 'YYYY-MM-DD 00:00:00'
            data["date_of_birth"] = parsed_date.strftime("%Y-%m-%d 00:00:00")

        return data

    def to_representation(self, instance):
        is_demo = self.context.get("is_demo", False)
        lang = self.context.get("lang", "en")
        
        source_instance = instance
        # if is_demo and isinstance(instance, Person):
        #     demo_person = DemoPerson.objects.filter(
        #         Q(mobile_number1=instance.mobile_number1) | Q(mobile_number2=instance.mobile_number1)
        #     ).first()
        #     if demo_person:
        #         source_instance = demo_person
        #         # Ensure all fields are accessible on DemoPerson to avoid AttributeError during serialization
        #         for field_name in self.Meta.fields:
        #             if not hasattr(source_instance, field_name):
        #                 if field_name == "profile" or field_name == "thumb_profile":
        #                     setattr(source_instance, field_name, getattr(source_instance, "profile_pic", None))
        #                 else:
        #                     setattr(source_instance, field_name, None)

        data = super().to_representation(source_instance)
        
        # Profile URLs
        profile_img = getattr(source_instance, 'profile', None) or getattr(source_instance, 'profile_pic', None)
        thumb_img   = getattr(source_instance, 'thumb_profile', None) or getattr(source_instance, 'profile_pic', None)

        if profile_img:
            try:
                data["profile"] = profile_img.url
            except Exception:
                data["profile"] = os.getenv("DEFAULT_PROFILE_PATH", "")
        else:
            data["profile"] = os.getenv("DEFAULT_PROFILE_PATH", "")

        if thumb_img:
            try:
                data["thumb_profile"] = thumb_img.url
            except Exception:
                data["thumb_profile"] = os.getenv("DEFAULT_PROFILE_PATH", "")
        else:
            data["thumb_profile"] = os.getenv("DEFAULT_PROFILE_PATH", "")

        if lang == "guj":
            if is_demo:
                data["first_name"] = source_instance.guj_first_name or source_instance.first_name
                data["middle_name"] = source_instance.guj_middle_name or source_instance.middle_name
                data["address"] = source_instance.address
                data["out_of_address"] = source_instance.out_of_address
            else:
                translate_data = TranslatePerson.objects.filter(
                    person_id=source_instance.id, language="guj", is_deleted=False
                ).first()
                if translate_data:
                    data["first_name"] = translate_data.first_name or source_instance.first_name
                    data["middle_name"] = translate_data.middle_name or source_instance.middle_name
                    data["address"] = translate_data.address or source_instance.address
                    data["out_of_address"] = translate_data.out_of_address or source_instance.out_of_address

            data["surname"] = self.get_surname(source_instance)
            data["city"] = self.get_city(source_instance)
            data["state"] = self.get_state(source_instance)
            data["village_name"] = self.get_village_name(source_instance)
            data["taluka_name"] = self.get_taluka_name(source_instance)
            data["district_name"] = self.get_district_name(source_instance)
        
        # Consistent field naming for surname
        if source_instance.surname:
            data["surname"] = self.get_surname(source_instance)
            
        return data

class CountrySummarySerializer(serializers.Serializer):
    country_id = serializers.IntegerField()
    country_name = serializers.CharField()
    flag = serializers.SerializerMethodField()
    total_members = serializers.IntegerField()

    def get_flag(self, obj):
        flag_path = obj.get('flag')
        if flag_path:
            # We don't have access to request build_absolute_uri easily here without context,
            # but usually returning the path or media URL works.
            # DRF's ImageField automatically adds MEDIA_URL if it was a ModelSerializer.
            # Since this is a regular Serializer, we can construct the media url.
            return f"{settings.MEDIA_URL}{flag_path}"
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.context.get("lang") == "guj":
            data["country_name"] = instance.get("guj_name")
        return data

# new serializer added ended. 

class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = [
            "id",
            "first_name",
            "middle_name",
            "address",
            "is_same_as_father_address",
            "is_same_as_son_address",
            "out_of_address",
            "date_of_birth",
            "blood_group",
            "city",
            "state",
            "out_of_country",
            "out_of_mobile",
            "flag_show",
            "mobile_number1",
            "mobile_number2",
            "profile",
            "thumb_profile",
            "status",
            "surname",
            "is_admin",
            "is_super_admin",
            "is_registered_directly",
            "update_field_message",
            "platform",
            "trans_first_name",
            "trans_middle_name",
            "district",
            "taluka",
            "village",
            "samaj",
        ]
    trans_first_name = serializers.SerializerMethodField(read_only=True, required=False)
    trans_middle_name = serializers.SerializerMethodField(read_only=True, required=False)
    district = serializers.SerializerMethodField(read_only=True, required=False)
    taluka = serializers.SerializerMethodField(read_only=True, required=False)
    village = serializers.SerializerMethodField(read_only=True, required=False)

    def get_trans_first_name(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        if translate_data and translate_data.first_name:
            return translate_data.first_name
        return obj.guj_first_name if hasattr(obj, 'guj_first_name') and obj.guj_first_name else obj.first_name

    def get_trans_middle_name(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        if translate_data and translate_data.middle_name:
            return translate_data.middle_name
        return obj.guj_middle_name if hasattr(obj, 'guj_middle_name') and obj.guj_middle_name else obj.middle_name

    def get_surname(self, obj):
        lang = self.context.get("lang", "en")
        if obj.surname:
            if lang == "guj" and obj.surname.guj_name:
                return obj.surname.guj_name
            return obj.surname.name
        return None

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        lang = self.context.get("lang", "en")
        if instance.surname:
            if lang == "guj" and instance.surname.guj_name:
                representation["surname"] = instance.surname.guj_name
            else:
                representation["surname"] = instance.surname.name
        else:
            representation["surname"] = ""
        return representation
    
    def get_village(self, obj):
        lang = self.context.get("lang", "en")
        if obj.samaj and obj.samaj.village:
            if lang == "guj" and obj.samaj.village.guj_name:
                return obj.samaj.village.guj_name
            return obj.samaj.village.name
        return ""

    def get_taluka(self, obj):
        lang = self.context.get("lang", "en")
        if obj.samaj and obj.samaj.village and obj.samaj.village.taluka:
            taluka = obj.samaj.village.taluka
            if lang == "guj" and taluka.guj_name:
                return taluka.guj_name
            return taluka.name
        return ""

    def get_district(self, obj):
        lang = self.context.get("lang", "en")
        if (
            obj.samaj
            and obj.samaj.village
            and obj.samaj.village.taluka
            and obj.samaj.village.taluka.district
        ):
            district = obj.samaj.village.taluka.district
            if lang == "guj" and district.guj_name:
                return district.guj_name
            return district.name
        return ""

    def validate(self, data):
        import re
        from django.db.models import Q
        from .models import Person

        # ---------- MOBILE VALIDATION ----------
        mobile_number1 = (data.get("mobile_number1") or "").strip()
        mobile_number2 = (data.get("mobile_number2") or "").strip()

        mobile_numbers = [m for m in [mobile_number1, mobile_number2] if m]

        # allow empty mobiles
        if mobile_numbers:

            # format validation
            for num in mobile_numbers:
                if not re.match(r"^\d{7,14}$", num):
                    raise serializers.ValidationError({
                        "message": "Mobile number must be 7-14 digits only."
                    })

            # same number check
            if len(mobile_numbers) == 2 and mobile_number1 == mobile_number2:
                raise serializers.ValidationError({
                    "message": "Mobile number 1 and 2 cannot be same."
                })

            # uniqueness check
            person_id = self.instance.id if self.instance else None

            query = Q()
            for num in mobile_numbers:
                query |= Q(mobile_number1=num) | Q(mobile_number2=num)

            existing = Person.objects.filter(query, is_deleted=False)

            if person_id:
                existing = existing.exclude(id=person_id)

            if existing.exists():
                raise serializers.ValidationError({
                    "message": "Mobile number already registered."
                })

        return data

# class DemoPersonSerializer(PersonSerializer):
#     class Meta(PersonSerializer.Meta):
#         model = DemoPerson

#     def get_blood_group(self, obj):
#         return ""

#     def validate(self, data):

#         first_name = data.get("first_name")
#         if not first_name:
#             raise serializers.DjangoValidationError(
#                 {"message": "First name is required."}
#             )
#         # pattern = r'^[a-zA-Z\s\-]{1,50}$'
#         # if not re.match(pattern, first_name):
#         #     raise serializers.ValidationError(
#         #         {"message": "First name can only contain letters, spaces, and hyphens."}
#         #     )

#         middle_name = data.get("middle_name")
#         if not middle_name:
#             raise serializers.DjangoValidationError(
#                 {"message": "Middle name is required."}
#             )
#         # pattern = r'^[a-zA-Z\s\-]{1,50}$'
#         # if not re.match(pattern, middle_name):
#         #     raise serializers.ValidationError(
#         #         {"message": "Middle name can only contain letters, spaces, and hyphens."}
#         #     )

#         # address = data.get("address")
#         # if address:
#         #     pattern = r'^[a-zA-Z0-9\s\-.,/#]+$'
#         #     if not re.match(pattern, address):
#         #         raise serializers.ValidationError(
#         #             {"message": "Address can only contain letters, numbers, spaces, "
#         #                         "hyphens, comma, period, slash, and pound sign."}
#         #         )

#         # out_of_address = data.get("out_of_address")
#         # if out_of_address:
#         #     pattern = r'^[a-zA-Z0-9\s\-.,/#]+$'
#         #     if not re.match(pattern, out_of_address):
#         #         raise serializers.ValidationError(
#         #             {"message": "Out Of Address can only contain letters, numbers, spaces, "
#         #                         "hyphens, comma, period, slash, and pound sign."}
#         #         )

#         # blood_group = data.get("blood_group", None)
#         # if blood_group is None:
#         #     raise serializers.DjangoValidationError({"message":"Blood group is required."})

#         # city = data.get("city")
#         # if not city:
#         #     raise serializers.DjangoValidationError({"message": "City is required."})

#         # district = data.get("district")
#         # if not district:
#         #     raise serializers.DjangoValidationError({"message": "District is required."})

#         flag_show = data.get("flag_show")
#         if flag_show and flag_show not in [True, False]:
#             raise serializers.DjangoValidationError(
#                 {"message": "Flag show must be a boolean value."}
#             )

#         # mobile_number1 = data.get("mobile_number1")
#         # mobile_number2 = data.get("mobile_number2")
#         # if (mobile_number1 and mobile_number1 is not "") or (mobile_number2 and  mobile_number2 is not ""):
#         #     query = None
#         #     person_id = self.context.get('person_id', 0)
#         #     if mobile_number1 and mobile_number1 != "":
#         #         query = Q(mobile_number1=mobile_number1) | Q(mobile_number2=mobile_number1)
#         #     if mobile_number2 and mobile_number2 != "":
#         #         if query:
#         #             query |= Q(mobile_number1=mobile_number2) | Q(mobile_number2=mobile_number2)
#         #         else:
#         #             query = Q(mobile_number1=mobile_number2) | Q(mobile_number2=mobile_number2)
#         #     if query :
#         #         mobile_exist = Person.objects.filter(query)
#         #         if person_id > 0 :
#         #             mobile_exist = mobile_exist.exclude(id=person_id)
#         #         if mobile_exist.exists():
#         #             raise serializers.ValidationError({"message": ["Mobile number is already registered."]})

#         mobile_number1 = data.get("mobile_number1")
#         mobile_number2 = data.get("mobile_number2")
#         mobile_numbers = [mobile_number1, mobile_number2]
#         for mobile_number in mobile_numbers:
#             if mobile_number and mobile_number.strip():
#                 if not re.match(r"^\d{7,14}$", mobile_number):
#                     raise serializers.ValidationError(
#                         {"message": ["Mobile number(s) can only contain digits (0-9)."]}
#                     )
#         person_id = self.context.get("person_id", 0)
#         query = None
#         for mobile_number in mobile_numbers:
#             if mobile_number:
#                 if query:
#                     query |= Q(mobile_number1=mobile_number) | Q(
#                         mobile_number2=mobile_number
#                     )
#                 else:
#                     query = Q(mobile_number1=mobile_number) | Q(
#                         mobile_number2=mobile_number
#                     )
#         if query:
#             mobile_exist = Person.objects.filter(query, is_deleted=False)
#             if person_id > 0:
#                 mobile_exist = mobile_exist.exclude(id=person_id, is_deleted=False)
#             if mobile_exist.exists():
#                 raise serializers.ValidationError(
#                     {"message": ["Mobile number is already registered."]}
#                 )

#         # surname = data.get("surname")
#         # if not surname:
#         #     raise serializers.DjangoValidationError({"message": "Surname is required."})

#         # is_admin = data.get("is_admin")
#         # if is_admin not in [True, False]:
#         #     raise serializers.DjangoValidationError({"message": "Is admin must be a boolean value."})

#         # is_registered_directly = data.get("is_registered_directly")
#         # if is_registered_directly not in [True, False]:
#         #     raise serializers.DjangoValidationError({"message": "Is registered directly must be a boolean value."})

#         # date_of_birth = data.get("date_of_birth")
#         # if not date_of_birth:
#         #     raise serializers.ValidationError({"message": "Date of birth is required."})
#         date_of_birth_str = data.get("date_of_birth")
#         if date_of_birth_str:
#             try:
#                 date_of_birth = datetime.strptime(
#                     date_of_birth_str, "%Y-%m-%d %H:%M:%S.%f"
#                 ).date()
#             except ValueError:
#                 raise serializers.ValidationError(
#                     {
#                         "message": "Invalid date format. Expected format: YYYY-MM-DD HH:MM:SS.SSS"
#                     }
#                 )

#         # try:
#         #     date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d %H:%M:%S.%f').date()
#         # except ValueError:
#         #     raise serializers.ValidationError({"message": "Date of birth must be in the format YYYY-MM-DD."})

#         # current_year = datetime.now().year
#         # if not (date(1947, 1, 1) <= date_of_birth <= date(current_year, 12, 31)):
#         #     raise serializers.ValidationError(
#         #         {"message": f"Date of birth must be between 1947 and {current_year}."}
#         #     )

#         return data

class PersonSerializerV2(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = [
            "id",
            "first_name",
            "middle_name",
            "trans_first_name",
            "trans_middle_name",
            "address",
            "is_same_as_father_address",
            "is_same_as_son_address",
            "out_of_address",
            "date_of_birth",
            "out_of_country",
            "out_of_mobile",
            "flag_show",
            "mobile_number1",
            "mobile_number2",
            "profile",
            "thumb_profile",
            "status",
            "surname",
            "village",
            "taluka",
            "district",
            "city",
            "state",
        ]
        extra_kwargs = {
            "city": {"required": False, "allow_null": True},
            "state": {"required": False, "allow_null": True},
        }

    trans_first_name = serializers.SerializerMethodField(read_only=True, required=False)
    trans_middle_name = serializers.SerializerMethodField(read_only=True, required=False)

    def get_trans_first_name(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        if translate_data and translate_data.first_name:
            return translate_data.first_name
        return obj.guj_first_name if hasattr(obj, 'guj_first_name') and obj.guj_first_name else obj.first_name

    def get_trans_middle_name(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        if translate_data and translate_data.middle_name:
            return translate_data.middle_name
        return obj.guj_middle_name if hasattr(obj, 'guj_middle_name') and obj.guj_middle_name else obj.middle_name

    def validate(self, data):

        first_name = data.get("first_name")
        if not first_name:
            raise serializers.DjangoValidationError(
                {"message": "First name is required."}
            )
        # pattern = r'^[a-zA-Z\s\-]{1,50}$'
        # if not re.match(pattern, first_name):
        #     raise serializers.ValidationError(
        #         {"message": "First name can only contain letters, spaces, and hyphens."}
        #     )

        middle_name = data.get("middle_name")
        if not middle_name:
            raise serializers.DjangoValidationError(
                {"message": "Middle name is required."}
            )
        

        flag_show = data.get("flag_show")
        if flag_show and flag_show not in [True, False]:
            raise serializers.DjangoValidationError(
                {"message": "Flag show must be a boolean value."}
            )

        mobile_number1 = (data.get("mobile_number1") or "").strip()
        mobile_number2 = (data.get("mobile_number2") or "").strip()

        if (not mobile_number1 or mobile_number1 == '') and mobile_number2 and mobile_number2 != '':
            data["mobile_number1"] = mobile_number2
            data["mobile_number2"] = None
        
        mobile_numbers = [mobile_number1, mobile_number2]
        for mobile_number in mobile_numbers:
            if mobile_number and mobile_number.strip():
                if not re.match(r"^\d{7,14}$", mobile_number):
                    raise serializers.ValidationError(
                        {"message": ["Mobile number(s) can only contain digits (0-9)."]}
                    )
        person_id = self.context.get("person_id", 0)
        query = None
        for mobile_number in mobile_numbers:
            if mobile_number:
                if query:
                    query |= Q(mobile_number1=mobile_number) | Q(
                        mobile_number2=mobile_number
                    )
                else:
                    query = Q(mobile_number1=mobile_number) | Q(
                        mobile_number2=mobile_number
                    )
        if query:
            mobile_exist = Person.objects.filter(query, is_deleted=False)
            if person_id > 0:
                mobile_exist = mobile_exist.exclude(id=person_id, is_deleted=False)
            if mobile_exist.exists():
                raise serializers.ValidationError(
                    {"message": ["Mobile number is already registered."]}
                )

    
        date_of_birth_str = data.get("date_of_birth")
        if date_of_birth_str:
            try:
                date_of_birth = datetime.strptime(
                    date_of_birth_str, "%Y-%m-%d %H:%M:%S.%f"
                ).date()
            except ValueError:
                raise serializers.ValidationError(
                    {
                        "message": "Invalid date format. Expected format: YYYY-MM-DD HH:MM:SS.SSS"
                    }
                )

        return data

# class DemoPersonSerializerV2(PersonSerializerV2):
#     class Meta(PersonSerializerV2.Meta):
#         model = DemoPerson

class AdminPersonGetSerializer(serializers.ModelSerializer):
    guj_first_name = serializers.SerializerMethodField(read_only=True, required=False)
    guj_middle_name = serializers.SerializerMethodField(read_only=True, required=False)
    guj_address = serializers.SerializerMethodField(read_only=True, required=False)
    guj_out_of_address = serializers.SerializerMethodField(
        read_only=True, required=False
    )
    # blood_group  = serializers.SerializerMethodField(read_only=True, required=False)
    city = serializers.SerializerMethodField(read_only=True, required=False)
    state = serializers.SerializerMethodField(read_only=True, required=False)
    out_of_country = serializers.SerializerMethodField(read_only=True, required=False)
    surname = serializers.SerializerMethodField(read_only=True, required=False)
    profile = serializers.SerializerMethodField(read_only=True, required=False)
    thumb_profile = serializers.SerializerMethodField(read_only=True, required=False)
    trans_first_name = serializers.SerializerMethodField(read_only=True, required=False)
    trans_middle_name = serializers.SerializerMethodField(read_only=True, required=False)
    village = serializers.SerializerMethodField(source="samaj.village", required=False)
    taluka = serializers.SerializerMethodField(source="samaj.taluka", required=False)
    district = serializers.SerializerMethodField(source="samaj.district", required=False)

    class Meta:
        model = Person
        fields = [
            "id",
            "first_name",
            "middle_name",
            "address",
            "is_same_as_son_address",
            "is_same_as_father_address",
            "out_of_address",
            "date_of_birth",
            "blood_group",
            "city",
            "state",
            "out_of_country",
            "flag_show",
            "mobile_number1",
            "mobile_number2",
            "profile",
            "thumb_profile",
            "status",
            "surname",
            "is_admin",
            "is_registered_directly",
            "guj_first_name",
            "guj_middle_name",
            "guj_address",
            "guj_out_of_address",
            "out_of_mobile",
            "trans_first_name",
            "trans_middle_name",
            "village",
            "taluka",
            "district",
        ]

    def get_profile(self, obj):
        if obj.profile:
            try:
                return obj.profile.url
            except Exception:
                pass
        return os.getenv("DEFAULT_PROFILE_PATH", "")

    def get_thumb_profile(self, obj):
        if obj.thumb_profile and obj.thumb_profile != "":
            try:
                return obj.thumb_profile.url
            except Exception:
                pass
        return os.getenv("DEFAULT_PROFILE_PATH", "")

    def get_guj_first_name(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        return translate_data.first_name if translate_data else ""

    def get_guj_middle_name(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        return translate_data.middle_name if translate_data else ""

    def get_guj_address(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        return translate_data.address if translate_data else ""

    def get_guj_out_of_address(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        return translate_data.out_of_address if translate_data else ""

    def get_city(self, obj):
        if obj.city is not None:
            lang = self.context.get("lang", "en")
            if lang == "guj":
                return obj.city.guj_name
            return obj.city.name
        return ""

    def get_state(self, obj):
        if obj.state is not None:
            lang = self.context.get("lang", "en")
            if lang == "guj":
                return obj.state.guj_name
            return obj.state.name
        return ""

    def get_village(self, obj):
        if obj.samaj and obj.samaj.village:
            lang = self.context.get("lang", "en")
            if lang == "guj":
                return obj.samaj.village.guj_name
            return obj.samaj.village.name
        return ""

    def get_taluka(self, obj):
        if obj.samaj and obj.samaj.village and obj.samaj.village.taluka:
            lang = self.context.get("lang", "en")
            if lang == "guj":
                return obj.samaj.village.taluka.guj_name
            return obj.samaj.village.taluka.name
        return ""

    def get_district(self, obj):
        if obj.samaj and obj.samaj.village and obj.samaj.village.taluka and obj.samaj.village.taluka.district:
            lang = self.context.get("lang", "en")
            if lang == "guj":
                return obj.samaj.village.taluka.district.guj_name
            return obj.samaj.village.taluka.district.name
        return ""

    def get_out_of_country(self, obj):
        if obj.out_of_country is not None:
            lang = self.context.get("lang", "en")
            if lang == "guj":
                return obj.out_of_country.guj_name
            else:
                return obj.out_of_country.name

        return ""

    def get_surname(self, obj):
        if obj.surname is not None:
            lang = self.context.get("lang", "en")
            if lang == "guj":
                return obj.surname.guj_name
            return obj.surname.name
        return ""

    def get_trans_first_name(self, obj):
        return self.get_guj_first_name(obj) or (obj.guj_first_name if hasattr(obj, 'guj_first_name') and obj.guj_first_name else obj.first_name)

    def get_trans_middle_name(self, obj):
        return self.get_guj_middle_name(obj) or (obj.guj_middle_name if hasattr(obj, 'guj_middle_name') and obj.guj_middle_name else obj.middle_name)

class CountryWiseMemberSerializer(serializers.ModelSerializer):
    surname = serializers.SerializerMethodField(read_only=True, required=False)
    profile = serializers.SerializerMethodField(read_only=True, required=False)
    thumb_profile = serializers.SerializerMethodField(read_only=True, required=False)
    trans_first_name = serializers.SerializerMethodField(read_only=True, required=False)
    trans_middle_name = serializers.SerializerMethodField(read_only=True, required=False)
    out_of_country = serializers.SerializerMethodField(read_only=True, required=False)

    class Meta:
        model = Person
        fields = [
            "id",
            "first_name",
            "middle_name",
            "date_of_birth",
            "mobile_number1",
            "mobile_number2",
            "flag_show",
            "profile",
            "is_admin",
            "surname",
            "thumb_profile",
            "trans_first_name",
            "trans_middle_name",
            "out_of_country",
        ]

    def get_surname(self, obj):
        lang = self.context.get("lang", "en")
        if not obj.surname:
            return None
        return obj.surname.guj_name if lang == "guj" and obj.surname.guj_name else obj.surname.name

    def get_profile(self, obj):
        if obj.profile and obj.profile.name:
            try:
                return obj.profile.url
            except Exception:
                pass
        return os.getenv("DEFAULT_PROFILE_PATH", "")

    def get_thumb_profile(self, obj):
        if obj.thumb_profile and obj.thumb_profile.name:
            try:
                return obj.thumb_profile.url
            except Exception:
                pass
        return os.getenv("DEFAULT_PROFILE_PATH", "")

    def get_trans_first_name(self, obj):
        if hasattr(obj, 'trans_fname'):
            return obj.trans_fname
            
        lang = self.context.get("lang", "en")
        if lang == "en":
            return None
            
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        if translate_data and translate_data.first_name:
            return translate_data.first_name
        return obj.guj_first_name if hasattr(obj, 'guj_first_name') and obj.guj_first_name else None

    def get_trans_middle_name(self, obj):
        if hasattr(obj, 'trans_mname'):
            return obj.trans_mname
            
        lang = self.context.get("lang", "en")
        if lang == "en":
            return None
            
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        if translate_data and translate_data.middle_name:
            return translate_data.middle_name
        return obj.guj_middle_name if hasattr(obj, 'guj_middle_name') and obj.guj_middle_name else None

    def get_thumb_profile(self, obj):
        if obj.thumb_profile and obj.thumb_profile != "":
            return obj.thumb_profile.url
        else:
            return os.getenv("DEFAULT_PROFILE_PATH")

    def get_guj_first_name(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        return translate_data.first_name if translate_data else ""

    def get_guj_middle_name(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        return translate_data.middle_name if translate_data else ""

    def get_guj_address(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        return translate_data.address if translate_data else ""

    def get_guj_out_of_address(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        return translate_data.out_of_address if translate_data else ""

    # def get_blood_group(self, obj):
    #     return obj.blood_group.bloodgroup

    def get_city(self, obj):
        return obj.city.name if obj.city else ""

    def get_state(self, obj):
        return obj.state.name if obj.state else ""

    def get_out_of_country(self, obj):
        if obj.out_of_country is not None:
            lang = self.context.get("lang", "en")
            if lang == "guj":
                return obj.out_of_country.guj_name
            else:
                return obj.out_of_country.name

        return ""

    def get_surname(self, obj):
        return obj.surname.name if obj.surname else ""

    def get_trans_first_name(self, obj):
        return self.get_guj_first_name(obj) or (obj.guj_first_name if hasattr(obj, 'guj_first_name') and obj.guj_first_name else obj.first_name)

    def get_trans_middle_name(self, obj):
        return self.get_guj_middle_name(obj) or (obj.guj_middle_name if hasattr(obj, 'guj_middle_name') and obj.guj_middle_name else obj.middle_name)

class PersonGetV4Serializer(serializers.ModelSerializer):

    city = serializers.SerializerMethodField(read_only=True, required=False)
    state = serializers.SerializerMethodField(read_only=True, required=False)
    out_of_country = serializers.SerializerMethodField(read_only=True, required=False)
    surname = serializers.SerializerMethodField(read_only=True, required=False)
    profile = serializers.SerializerMethodField(read_only=True, required=False)
    thumb_profile = serializers.SerializerMethodField(read_only=True, required=False)
    village = serializers.SerializerMethodField(read_only=True, required=False)
    taluka = serializers.SerializerMethodField(read_only=True, required=False)
    district = serializers.SerializerMethodField(read_only=True, required=False)
    samaj = serializers.SerializerMethodField(read_only=True)
    plan = serializers.SerializerMethodField(read_only=True)
    trans_first_name = serializers.SerializerMethodField(read_only=True, required=False)
    trans_middle_name = serializers.SerializerMethodField(read_only=True, required=False)

    # password = serializers.SerializerMethodField    (read_only=True)
    class Meta:
        model = Person
        fields = [
            "id",
            "first_name",
            "middle_name",
            "address",
            "is_same_as_son_address",
            "is_same_as_father_address",
            "out_of_address",
            "date_of_birth",
            "blood_group",
            "city",
            "state",
            "out_of_country",
            "flag_show",
            "is_super_admin",
            "mobile_number1",
            "out_of_mobile",
            "mobile_number2",
            "profile",
            "thumb_profile",
            "status",
            "surname",
            "is_super_uper",
            "is_admin",
            "password",
            "is_registered_directly",
            "is_deleted",
            "deleted_by",
            "is_show_old_contact",
            "taluka",
            "district",
            "village",
            "plan",
            "samaj",
            "trans_first_name",
            "trans_middle_name",
        ]

    # def get_password(self, obj) :
    #     is_password_required = self.context.get('is_password_required', False)
    #     if is_password_required :
    #         if obj.is_admin:
    #             return obj.password
    #     return ""

    def get_state(self, obj):
        if hasattr(obj, 'state') and obj.state is not None:
            lang = self.context.get("lang", "en")
            if lang == "guj":
                return obj.state.guj_name
            return obj.state.name
        return ""
    
    def get_city(self, obj):
        if hasattr(obj, 'city') and obj.city is not None:
            lang = self.context.get("lang", "en")
            if lang == "guj":
                return obj.city.guj_name
            return obj.city.name
        return ""

    def get_profile(self, obj):
        image = getattr(obj, 'profile', None) or getattr(obj, 'profile_pic', None)
        if image:
            try:
                return image.url
            except Exception:
                pass
        return os.getenv("DEFAULT_PROFILE_PATH", "")

    def get_thumb_profile(self, obj):
        image = getattr(obj, 'thumb_profile', None) or getattr(obj, 'profile_pic', None)
        if image:
            try:
                return image.url
            except Exception:
                pass
        return os.getenv("DEFAULT_PROFILE_PATH", "")
        
    def get_samaj(self, obj):
        lang = self.context.get("lang", "en")
        if obj.samaj:
            if lang == "guj" and obj.samaj.guj_name:
                return obj.samaj.guj_name
            return obj.samaj.name
        return ""

    # def get_taluka(self, obj):
    #     if hasattr(obj, 'taluka') and obj.taluka is not None:
    #         lang = self.context.get("lang", "en")
    #         if lang == "guj":
    #             return obj.taluka.guj_name
    #         return obj.taluka.name
    #     return "".
    def get_taluka(self, obj):
        lang = self.context.get("lang", "en")
        if obj.samaj and obj.samaj.village and obj.samaj.village.taluka:
            taluka = obj.samaj.village.taluka
            if lang == "guj" and taluka.guj_name:
                return taluka.guj_name
            return taluka.name
        return ""

    # def get_district(self, obj):
    #     if hasattr(obj, 'district') and obj.district is not None:
    #         lang = self.context.get("lang", "en")
    #         if lang == "guj":
    #             return obj.district.guj_name
    #         return obj.district.name
    #     return ""
    def get_district(self, obj):
        lang = self.context.get("lang", "en")
        if (
            obj.samaj
            and obj.samaj.village
            and obj.samaj.village.taluka
            and obj.samaj.village.taluka.district
        ):
            district = obj.samaj.village.taluka.district
            if lang == "guj" and district.guj_name:
                return district.guj_name
            return district.name
        return ""
    
    # def get_village(self, obj):
    #     if hasattr(obj, 'village') and obj.village is not None:
    #         lang = self.context.get("lang", "en")
    #         if lang == "guj":
    #             return obj.village.guj_name
    #         return obj.village.name
    #     return ""

    def get_village(self, obj):
        lang = self.context.get("lang", "en")
        if obj.samaj and obj.samaj.village:
            if lang == "guj" and obj.samaj.village.guj_name:
                return obj.samaj.village.guj_name
            return obj.samaj.village.name
        return ""
    

    def get_surname(self, obj):
        if obj.surname is not None:
            lang = self.context.get("lang", "en")
            if lang == "guj":
                return obj.surname.guj_name
            return obj.surname.name
        return ""
    
    def get_plan(self, obj):
        if obj.samaj:
            return obj.samaj.plan
        return "free"

    def get_out_of_country(self, obj):
        if hasattr(obj, "out_of_country") and obj.out_of_country:
            lang = self.context.get("lang", "en")
            if lang == "guj" and hasattr(obj.out_of_country, "guj_name"):
                return obj.out_of_country.guj_name
            return obj.out_of_country.name
        return ""

    def get_trans_first_name(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        if translate_data and translate_data.first_name:
            return translate_data.first_name
        return obj.guj_first_name if hasattr(obj, 'guj_first_name') and obj.guj_first_name else obj.first_name

    def get_trans_middle_name(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        if translate_data and translate_data.middle_name:
            return translate_data.middle_name
        return obj.guj_middle_name if hasattr(obj, 'guj_middle_name') and obj.guj_middle_name else obj.middle_name

    def to_representation(self, instance):
        # Handle missing fields for DemoPerson before serialization
        if self.context.get("is_demo", False):
            # Duck-type missing fields to None/Empty to avoid AttributeError in super().to_representation
            fields_to_mock = [
                "blood_group", "city", "out_of_mobile", "password", 
                "is_same_as_son_address", "is_same_as_father_address", 
                "status", "is_super_uper", "deleted_by", 
                "is_show_old_contact", "is_deleted"
            ]
            for field in fields_to_mock:
                if not hasattr(instance, field):
                   setattr(instance, field, None)

        representation = super().to_representation(instance)
        lang = self.context.get("lang", "en")
        is_demo = self.context.get("is_demo", False)
        
        if lang == "guj":
            if is_demo:
                 representation["first_name"] = instance.guj_first_name or instance.first_name
                 representation["middle_name"] = instance.guj_middle_name or instance.middle_name
                 # DemoPerson has no guj_address, keep default
            else:
                translate_data = TranslatePerson.objects.filter(
                    person_id=int(instance.id), is_deleted=False
                ).first()
                if translate_data:
                    representation["first_name"] = (
                        translate_data.first_name
                        if translate_data.first_name
                        else (instance.guj_first_name if hasattr(instance, 'guj_first_name') and instance.guj_first_name else instance.first_name)
                    )
                    representation["middle_name"] = (
                        translate_data.middle_name
                        if translate_data.middle_name
                        else (instance.guj_middle_name if hasattr(instance, 'guj_middle_name') and instance.guj_middle_name else instance.middle_name)
                    )
                    representation["address"] = (
                        translate_data.address
                        if translate_data.address
                        else instance.address
                    )
                    representation["out_of_address"] = (
                        translate_data.out_of_address
                        if translate_data.out_of_address
                        else instance.out_of_address
                    )

        return representation

class PersonGetSerializer(serializers.ModelSerializer):

    city = serializers.SerializerMethodField(read_only=True, required=False)
    state = serializers.SerializerMethodField(read_only=True, required=False)
    out_of_country = serializers.SerializerMethodField(read_only=True, required=False)
    surname = serializers.SerializerMethodField(read_only=True, required=False)
    profile = serializers.SerializerMethodField(read_only=True, required=False)
    thumb_profile = serializers.SerializerMethodField(read_only=True, required=False)

    # password = serializers.SerializerMethodField    (read_only=True)
    class Meta:
        model = Person
        fields = [
            "id",
            "first_name",
            "middle_name",
            "address",
            "is_same_as_son_address",
            "is_same_as_father_address",
            "out_of_address",
            "date_of_birth",
            "blood_group",
            "city",
            "state",
            "out_of_country",
            "flag_show",
            "is_super_admin",
            "mobile_number1",
            "out_of_mobile",
            "mobile_number2",
            "profile",
            "thumb_profile",
            "status",
            "surname",
            "is_super_uper",
            "is_admin",
            "password",
            "is_registered_directly",
            "is_deleted",
            "deleted_by",
            "is_show_old_contact",
            "trans_first_name",
            "trans_middle_name",
            "district",
            "taluka",
            "village",
            "samaj",
        ]

    district = serializers.SerializerMethodField(read_only=True, required=False)
    taluka = serializers.SerializerMethodField(read_only=True, required=False)
    village = serializers.SerializerMethodField(read_only=True, required=False)
    samaj = serializers.SerializerMethodField(read_only=True, required=False)

    def get_samaj(self, obj):
        lang = self.context.get("lang", "en")
        if obj.samaj:
            return obj.samaj.guj_name if lang == "guj" and obj.samaj.guj_name else obj.samaj.name
        return None

    def get_village(self, obj):
        lang = self.context.get("lang", "en")
        if obj.samaj and obj.samaj.village:
            if lang == "guj" and obj.samaj.village.guj_name:
                return obj.samaj.village.guj_name
            return obj.samaj.village.name
        return ""

    def get_taluka(self, obj):
        lang = self.context.get("lang", "en")
        if obj.samaj and obj.samaj.village and obj.samaj.village.taluka:
            taluka = obj.samaj.village.taluka
            if lang == "guj" and taluka.guj_name:
                return taluka.guj_name
            return taluka.name
        return ""

    def get_district(self, obj):
        lang = self.context.get("lang", "en")
        if (
            obj.samaj
            and obj.samaj.village
            and obj.samaj.village.taluka
            and obj.samaj.village.taluka.district
        ):
            district = obj.samaj.village.taluka.district
            if lang == "guj" and district.guj_name:
                return district.guj_name
            return district.name
        return ""

    # def get_password(self, obj) :
    #     is_password_required = self.context.get('is_password_required', False)
    #     if is_password_required :
    #         if obj.is_admin:
    #             return obj.password
    #     return ""

    def get_city(self, obj):
        if obj.city is not None:
            lang = self.context.get("lang", "en")
            if lang == "guj":
                return obj.city.guj_name
            return obj.city.name
        return ""

    def get_profile(self, obj):
        if obj.profile:
            try:
                return obj.profile.url
            except Exception:
                pass
        return os.getenv("DEFAULT_PROFILE_PATH", "")

    def get_thumb_profile(self, obj):
        if obj.thumb_profile and obj.thumb_profile != "":
            try:
                return obj.thumb_profile.url
            except Exception:
                pass
        return os.getenv("DEFAULT_PROFILE_PATH", "")

    def get_state(self, obj):
        if obj.state is not None:
            lang = self.context.get("lang", "en")
            if lang == "guj":
                return obj.state.guj_name
            return obj.state.name
        return ""

    def get_out_of_country(self, obj):
        if obj.out_of_country is not None:
            lang = self.context.get("lang", "en")
            if lang == "guj":
                return obj.out_of_country.guj_name
            return obj.out_of_country.name
        return ""

    def get_surname(self, obj):
        if obj.surname is not None:
            lang = self.context.get("lang", "en")
            if lang == "guj":
                return obj.surname.guj_name
            return obj.surname.name
        return ""

    trans_first_name = serializers.SerializerMethodField(read_only=True, required=False)
    trans_middle_name = serializers.SerializerMethodField(read_only=True, required=False)

    def get_trans_first_name(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        if translate_data and translate_data.first_name:
            return translate_data.first_name
        return obj.guj_first_name if hasattr(obj, 'guj_first_name') and obj.guj_first_name else obj.first_name

    def get_trans_middle_name(self, obj):
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.id, language="guj", is_deleted=False
        ).first()
        if translate_data and translate_data.middle_name:
            return translate_data.middle_name
        return obj.guj_middle_name if hasattr(obj, 'guj_middle_name') and obj.guj_middle_name else obj.middle_name

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        lang = self.context.get("lang", "en")
        if lang == "guj":
            translate_data = TranslatePerson.objects.filter(
                person_id=int(instance.id), is_deleted=False
            ).first()
            if translate_data:
                representation["first_name"] = (
                    translate_data.first_name
                    if translate_data.first_name
                    else (instance.guj_first_name if hasattr(instance, 'guj_first_name') and instance.guj_first_name else instance.first_name)
                )
                representation["middle_name"] = (
                    translate_data.middle_name
                    if translate_data.middle_name
                    else (instance.guj_middle_name if hasattr(instance, 'guj_middle_name') and instance.guj_middle_name else instance.middle_name)
                )
                representation["address"] = (
                    translate_data.address
                    if translate_data.address
                    else instance.address
                )
                representation["out_of_address"] = (
                    translate_data.out_of_address
                    if translate_data.out_of_address
                    else instance.out_of_address
                )
        return representation

class PersonGetSerializer2(PersonGetSerializer):
    
    update_field_message = serializers.SerializerMethodField(read_only=True)

    class Meta(PersonGetSerializer.Meta):
        fields = PersonGetSerializer.Meta.fields + [
            "update_field_message"
        ]

    def get_update_field_message(self, obj):
        """
        obj.update_field_message is stored as string.
        Example:
        "[{'field': 'a', 'previous': None, 'new': 'x'}, ...]"
        We return: "a, b, c"
        """
        if not obj.update_field_message:
            return ""

        try:
            print("obj.update_field_message --- ", obj.update_field_message)
            # Convert string into Python list
            list_data = ast.literal_eval(obj.update_field_message)
            print(list_data)
            # Extract 'field' values
            field_names = [item.get("field") for item in list_data if "field" in item]

            # Return concatenated names
            return ", ".join(field_names)

        except Exception as e:
            print(e)
            # In case string is invalid or not parseable
            return ""

class PersonGetSerializer4(PersonGetV4Serializer):
    
    update_field_message = serializers.SerializerMethodField(read_only=True)

    class Meta(PersonGetV4Serializer.Meta):
        fields = PersonGetV4Serializer.Meta.fields + [
            "update_field_message"
        ]

    def get_update_field_message(self, obj):
        """
        obj.update_field_message is stored as string.
        Example:
        "[{'field': 'a', 'previous': None, 'new': 'x'}, ...]"
        We return: "a, b, c"
        """
        if not obj.update_field_message:
            return ""

        try:
            print("obj.update_field_message --- ", obj.update_field_message)
            # Convert string into Python list
            list_data = ast.literal_eval(obj.update_field_message)
            print(list_data)
            # Extract 'field' values
            field_names = [item.get("field") for item in list_data if "field" in item]

            # Return concatenated names
            return ", ".join(field_names)

        except Exception as e:
            print(e)
            # In case string is invalid or not parseable
            return ""

class TranslatePersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = TranslatePerson
        fields = [
            "person_id",
            "first_name",
            "middle_name",
            "address",
            "out_of_address",
            "language",
        ]

class DemoTranslatePersonSerializer(TranslatePersonSerializer):
    pass

class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ["id", "name"]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        lang = self.context.get("lang", "en")
        if lang == "guj":
            representation["name"] = (
                instance.guj_name if instance.guj_name else instance.name
            )
        else:
            representation["name"] = instance.name
        return representation

class StateSerializer(serializers.ModelSerializer):
    class Meta:
        model = State
        fields = ["id", "name"]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        lang = self.context.get("lang", "en")
        if lang == "guj":
            representation["name"] = (
                instance.guj_name if instance.guj_name else instance.name
            )
        else:
            representation["name"] = instance.name
        return representation

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["id", "name"]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        lang = self.context.get("lang", "en")
        if lang == "guj":
            representation["name"] = (
                instance.guj_name if instance.guj_name else instance.name
            )
        else:
            representation["name"] = instance.name
        return representation

class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = [
            "id",
            "redirect_url",
            "images",
            "created_person",
            "is_active",
            "is_ad_lable",
            "expire_date",
        ]

class BannerGETSerializer(serializers.ModelSerializer):
    created_date = serializers.SerializerMethodField()

    class Meta:
        model = Banner
        fields = [
            "id",
            "redirect_url",
            "images",
            "is_active",
            "is_ad_lable",
            "expire_date",
            "created_date",
        ]

    def get_created_date(self, obj):
        # Format the created_date to show only the date part
        return obj.created_date.date()

class ParentChildRelationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentChildRelation
        fields = ["id", "parent", "child", "created_user"]

    # def validate(self, data):
    #     parent_id = data.get('parent')
    #     child_id = data.get('child')
    #     if parent_id == child_id:
    #         raise serializers.ValidationError("Parent ID and Child ID cannot be the same.")
    #     existing_relations = ParentChildRelation.objects.filter((Q(parent=parent_id) & Q(child=child_id)) | (Q(child=parent_id) & Q(parent=child_id)))
    #     if existing_relations.exists():
    #         raise serializers.ValidationError("A relation with these parent and child IDs already exists.")
    #     return data

    def validate(self, data):
        parent_id = data.get("parent")
        child_id = data.get("child")
        if parent_id == child_id:
            raise serializers.ValidationError(
                "Parent ID and Child ID cannot be the same."
            )
        existing_relations = ParentChildRelation.objects.filter(
            Q(parent=parent_id) & Q(child=child_id)
            | Q(child=parent_id) & Q(parent=child_id),
            is_deleted=False,
        )
        if existing_relations.exists():
            if self.instance:
                existing_relation = existing_relations.filter(pk=self.instance.pk)
                if not existing_relation.exists():
                    raise serializers.ValidationError(
                        "A relation with these parent and child IDs already exists."
                    )
            else:
                raise serializers.ValidationError(
                    "A relation with these parent and child IDs already exists."
                )
        return data

# class DemoParentChildRelationSerializer(ParentChildRelationSerializer):
#     class Meta(ParentChildRelationSerializer.Meta):
#         model = DemoParentChildRelation

    # def validate(self, data):
    #     parent_id = data.get("parent")
    #     child_id = data.get("child")
    #     if parent_id == child_id:
    #         raise serializers.ValidationError(
    #             "Parent ID and Child ID cannot be the same."
    #         )
    #     existing_relations = DemoParentChildRelation.objects.filter(
    #         Q(parent=parent_id) & Q(child=child_id)
    #         | Q(child=parent_id) & Q(parent=child_id),
    #         is_deleted=False,
    #     )
    #     if existing_relations.exists():
    #         if self.instance:
    #             existing_relation = existing_relations.filter(pk=self.instance.pk)
    #             if not existing_relation.exists():
    #                 raise serializers.ValidationError(
    #                     "A relation with these parent and child IDs already exists."
    #                 )
    #         else:
    #             raise serializers.ValidationError(
    #                 "A relation with these parent and child IDs already exists."
    #             )
    #     return data

class GetParentChildRelationSerializer(serializers.ModelSerializer):
    parent = PersonGetSerializer(read_only=True)
    child = PersonGetSerializer(read_only=True)
    created_user = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ParentChildRelation
        fields = ["id", "parent", "child", "created_user"]

    def get_created_user(self, obj):
        lang = self.context.get("lang", "en")
        is_demo = self.context.get("is_demo", False)
        if lang == "guj":
            if is_demo:
                return (obj.created_user.guj_first_name or obj.created_user.first_name) + " " + (obj.created_user.guj_middle_name or obj.created_user.middle_name)
            
            translate_data = TranslatePerson.objects.filter(
                person_id=int(obj.created_user.id), is_deleted=False
            ).first()
            if translate_data:
                return translate_data.first_name + " " + translate_data.middle_name
        return obj.created_user.first_name + " " + obj.created_user.middle_name

    def to_representation(self, instance):
        # Call the superclass method to get the original representation
        representation = super().to_representation(instance)
        return representation

class GetTreeRelationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentChildRelation
        fields = ["id", "parent", "child", "trans_first_name", "trans_middle_name"]

    trans_first_name = serializers.SerializerMethodField(read_only=True, required=False)
    trans_middle_name = serializers.SerializerMethodField(read_only=True, required=False)

    def get_trans_first_name(self, obj):
        if not obj.child:
            return None
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.child.id, language="guj", is_deleted=False
        ).first()
        if translate_data and translate_data.first_name:
            return translate_data.first_name
        return obj.child.guj_first_name if hasattr(obj.child, 'guj_first_name') and obj.child.guj_first_name else obj.child.first_name

    def get_trans_middle_name(self, obj):
        if not obj.child:
            return None
        translate_data = TranslatePerson.objects.filter(
            person_id=obj.child.id, language="guj", is_deleted=False
        ).first()
        if translate_data and translate_data.middle_name:
            return translate_data.middle_name
        return obj.child.guj_middle_name if hasattr(obj.child, 'guj_middle_name') and obj.child.guj_middle_name else obj.child.middle_name

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ["profile", "thumb_profile", "id"]

class ChildPersonSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField(read_only=True, required=False)
    thumb_profile = serializers.SerializerMethodField(read_only=True, required=False)

    class Meta:
        model = Person
        fields = "__all__"
        depth = 1

    def get_profile(self, obj):
        if obj.profile:
            return obj.profile.url
        else:
            return os.getenv("DEFAULT_PROFILE_PATH")

    def get_thumb_profile(self, obj):
        if obj.thumb_profile and obj.thumb_profile != "":
            return obj.thumb_profile.url
        else:
            return os.getenv("DEFAULT_PROFILE_PATH")

class PersonDataAdminSerializer(serializers.ModelSerializer):
    surname = serializers.SerializerMethodField(read_only=True, required=False)
    profile = serializers.SerializerMethodField(read_only=True, required=False)
    thumb_profile = serializers.SerializerMethodField(read_only=True, required=False)

    class Meta:
        model = Person
        fields = [
            "id",
            "first_name",
            "middle_name",
            "surname",
            "date_of_birth",
            "mobile_number1",
            "mobile_number2",
            "address",
            "is_same_as_son_address",
            "is_same_as_father_address",
            "out_of_address",
            "out_of_mobile",
            "blood_group",
            "city",
            "state",
            "out_of_country",
            "flag_show",
            "profile",
            "thumb_profile",
            "status",
            "is_admin",
            "is_super_admin",
            "password",
            "is_registered_directly",
            "is_deleted",
            "deleted_by",
        ]

    def get_surname(self, obj):
        lang = self.context.get("lang", "en")
        if lang == "guj":
            return obj.surname.guj_name
        return obj.surname.name

    def get_profile(self, obj):
        if obj.profile:
            return obj.profile.url
        else:
            return os.getenv("DEFAULT_PROFILE_PATH")

    def get_thumb_profile(self, obj):
        if obj.thumb_profile and obj.thumb_profile != "":
            return obj.thumb_profile.url
        else:
            return os.getenv("DEFAULT_PROFILE_PATH")

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        lang = self.context.get("lang", "en")
        if lang == "guj":
            translate_data = TranslatePerson.objects.filter(
                person_id=int(instance.id), is_deleted=False
            ).first()
            if translate_data:
                representation["first_name"] = (
                    translate_data.first_name
                    if translate_data.first_name
                    else (instance.guj_first_name if hasattr(instance, 'guj_first_name') and instance.guj_first_name else instance.first_name)
                )
                representation["middle_name"] = (
                    translate_data.middle_name
                    if translate_data.middle_name
                    else (instance.guj_middle_name if hasattr(instance, 'guj_middle_name') and instance.guj_middle_name else instance.middle_name)
                )
                representation["address"] = (
                    translate_data.address
                    if translate_data.address
                    else instance.address
                )
                representation["out_of_address"] = (
                    translate_data.out_of_address
                    if translate_data.out_of_address
                    else instance.out_of_address
                )
        return representation

class GetSurnameSerializerdata(serializers.ModelSerializer):
    class Meta:
        model = Surname
        fields = ["name"]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        lang = self.context.get("lang", "en")
        if lang == "guj":
            representation["name"] = (
                instance.guj_name if instance.guj_name else instance.name
            )
        else:
            representation["name"] = instance.name
        return representation

class PersonGetDataSortSerializer(serializers.ModelSerializer):
    surname = serializers.SerializerMethodField(read_only=True, required=False)
    trans_first_name = serializers.SerializerMethodField(read_only=True, required=False)
    trans_middle_name = serializers.SerializerMethodField(
        read_only=True, required=False
    )
    profile = serializers.SerializerMethodField(read_only=True, required=False)
    thumb_profile = serializers.SerializerMethodField(read_only=True, required=False)

    class Meta:
        model = Person
        fields = [
            "id",
            "first_name",
            "middle_name",
            "trans_first_name",
            "trans_middle_name",
            "flag_show",
            "date_of_birth",
            "mobile_number1",
            "mobile_number2",
            "profile",
            "thumb_profile",
            "surname",
            "is_admin",
            "is_super_admin",
        ]

    def get_profile(self, obj):
        if obj.profile:
            return obj.profile.url
        else:
            return os.getenv("DEFAULT_PROFILE_PATH")

    def get_thumb_profile(self, obj):
        if obj.thumb_profile and obj.thumb_profile != "":
            return obj.thumb_profile.url
        else:
            return os.getenv("DEFAULT_PROFILE_PATH")

    def get_surname(self, obj):
        if obj.surname is not None:
            lang = self.context.get("lang", "en")
            if lang == "guj":
                return obj.surname.guj_name
            return obj.surname.name
        return ""

    def get_trans_first_name(self, obj):
        if obj.first_name is not None:

            lang = self.context.get("lang", "en")
            if lang == "en":
                try:
                    translate_data = TranslatePerson.objects.filter(
                        person_id=int(obj.id), is_deleted=False
                    ).first()
                    return translate_data.first_name
                except Exception as e:
                    pass
            else:
                try:
                    translate_data = Person.objects.filter(id=int(obj.id)).first()
                    return translate_data.first_name
                except Exception as e:
                    pass
        return ""

    def get_trans_middle_name(self, obj):
        if obj.middle_name is not None:
            lang = self.context.get("lang", "en")
            if lang == "en":
                try:
                    translate_data = TranslatePerson.objects.filter(
                        person_id=int(obj.id), is_deleted=False
                    ).first()
                    return translate_data.middle_name
                except Exception as e:
                    pass
            else:
                try:
                    translate_data = Person.objects.filter(id=int(obj.id)).first()
                    return translate_data.middle_name
                except Exception as e:
                    pass
        return ""

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        lang = self.context.get("lang", "en")
        if lang == "guj":
            translate_data = TranslatePerson.objects.filter(
                person_id=int(instance.id), is_deleted=False
            ).first()
            if translate_data:
                representation["first_name"] = (
                    translate_data.first_name
                    if translate_data.first_name
                    else (instance.guj_first_name if hasattr(instance, 'guj_first_name') and instance.guj_first_name else instance.first_name)
                )
                representation["middle_name"] = (
                    translate_data.middle_name
                    if translate_data.middle_name
                    else (instance.guj_middle_name if hasattr(instance, 'guj_middle_name') and instance.guj_middle_name else instance.middle_name)
                )

        return representation

class RelationtreePersonSerializer(serializers.ModelSerializer):
    trans_first_name = serializers.SerializerMethodField(read_only=True)
    trans_middle_name = serializers.SerializerMethodField(read_only=True)
    profile = serializers.SerializerMethodField(read_only=True)
    thumb_profile = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Person
        fields = [
            "id",
            "date_of_birth",
            "profile",
            "thumb_profile",
            "mobile_number1",
            "mobile_number2",
            "out_of_country",
            "flag_show",
            "emoji",
            "trans_first_name",
            "trans_middle_name",
        ]

    def get_trans_first_name(self, obj):
        lang = self.context.get("lang", "en")
        is_demo = self.context.get("is_demo", False)
        if is_demo:
            return obj.guj_first_name if lang == "guj" and obj.guj_first_name else obj.first_name
        
        if lang == "guj":
            translate_data = TranslatePerson.objects.filter(
                person_id=obj.id, language="guj", is_deleted=False
            ).first()
            return translate_data.first_name if translate_data else obj.first_name
        return obj.first_name

    def get_trans_middle_name(self, obj):
        lang = self.context.get("lang", "en")
        is_demo = self.context.get("is_demo", False)
        if is_demo:
            return obj.guj_middle_name if lang == "guj" and obj.guj_middle_name else obj.middle_name
        
        if lang == "guj":
            translate_data = TranslatePerson.objects.filter(
                person_id=obj.id, language="guj", is_deleted=False
            ).first()
            return translate_data.middle_name if translate_data else obj.middle_name
        return obj.middle_name

    def get_profile(self, obj):
        if obj.profile:
            return obj.profile.url
        return os.getenv("DEFAULT_PROFILE_PATH")

    def get_thumb_profile(self, obj):
        if obj.thumb_profile:
            return obj.thumb_profile.url
        return os.getenv("DEFAULT_PROFILE_PATH")

class V4RelationTreeSerializer(serializers.ModelSerializer):
    parent = RelationtreePersonSerializer(read_only=True)
    child = RelationtreePersonSerializer(read_only=True)

    class Meta:
        model = ParentChildRelation
        fields = ["id", "parent", "child"]
