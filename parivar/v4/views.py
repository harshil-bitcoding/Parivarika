from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from django.db.models import Q, Count, Case, When, F, IntegerField, Value
from django.db.models.functions import Cast, Coalesce
from django.db.models import Case, When, Value, F, CharField, Q
from django.core import signing
from django.urls import reverse

from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.db.models.functions import Concat
from django.db import transaction, IntegrityError
from datetime import datetime, timedelta
import numpy as np
import cv2
import string
import random
from ..models import (
    Person, District, Taluka, User, Village, Samaj, State, 
    TranslatePerson, Surname, ParentChildRelation, Country,
    BloodGroup, Banner, AdsSetting, PersonUpdateLog, RandomBanner,
    # DemoPerson, DemoParentChildRelation, DemoSurname
)
# from ..services import LocationResolverService, CSVImportService
from django.conf import settings
from notifications.models import PersonPlayerId
from ..serializers import (
    DistrictSerializer,
    StateSerializer, 
    TalukaSerializer, 
    VillageSerializer,
    SamajSerializer,
    PersonV4Serializer,
    SurnameSerializer,
    BloodGroupSerializer,
    ProfileSerializer,
    PersonSerializer,
    AdminPersonGetSerializer,
    GetParentChildRelationSerializer,
    PersonGetSerializer,
    GetSurnameSerializer,
    GetTreeRelationSerializer,
    GetSurnameSerializerdata,
    PersonDataAdminSerializer,
    BannerSerializer,
    BannerGETSerializer,
    PersonGetDataSortSerializer,
    ParentChildRelationSerializer,
    PersonSerializerV2,
    PersonGetSerializer2,
    TranslatePersonSerializer,
    CitySerializer,
    CountrySerializer,
    V4RelationTreeSerializer,
    # DemoPersonSerializer,
    # DemoPersonSerializerV2,
    # DemoParentChildRelationSerializer,
    DemoTranslatePersonSerializer,
)
from ..views import getadmincontact
import logging
import os
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from random import choices
import logging

logger = logging.getLogger(__name__)

class DistrictDetailView(APIView):
    @swagger_auto_schema(
        operation_description="Get all districts",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING)
        ],
        responses={200: openapi.Response(description="Districts list", schema=DistrictSerializer(many=True))}
    )
    def get(self, request):
        lang = request.GET.get("lang", "en")
        districts = District.objects.filter(is_active=True)
        serializer = DistrictSerializer(districts, many=True, context={"lang": lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

class TalukaDetailView(APIView):
    @swagger_auto_schema(
        operation_description="Get talukas by district ID",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING)
        ],
        responses={200: openapi.Response(description="Talukas list", schema=TalukaSerializer(many=True))}
    )
    def get(self, request, district_id):
        lang = request.GET.get("lang", "en")
        talukas = Taluka.objects.filter(
            district_id=district_id, 
            is_active=True, 
            district__is_active=True
        )
        serializer = TalukaSerializer(talukas, many=True, context={"lang": lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

class VillageDetailView(APIView):
    @swagger_auto_schema(
        operation_description="Get villages by taluka ID",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING)
        ],
        responses={200: openapi.Response(description="Villages list", schema=VillageSerializer(many=True))}
    )
    def get(self, request, taluka_id):
        lang = request.GET.get("lang", "en")
        villages = Village.objects.filter(
            taluka_id=taluka_id, 
            is_active=True, 
            taluka__is_active=True, 
            taluka__district__is_active=True
        )
        serializer = VillageSerializer(villages, many=True, context={"lang": lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

class SamajListView(APIView):
    """Returns all samaj."""
    @swagger_auto_schema(
        operation_description="Get all samaj",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING)
        ],
        responses={200: openapi.Response(description="Samaj list", schema=SamajSerializer(many=True))}
    )
    def get(self, request):
        lang = request.GET.get("lang", "en")
        samaj = Samaj.objects.all().order_by('name')
        serializer = SamajSerializer(samaj, many=True, context={"lang": lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

class SamajByVillageView(APIView):
    """Returns samaj present in a specific village."""
    @swagger_auto_schema(
        operation_description="Get samaj in a specific village",
        manual_parameters=[
            openapi.Parameter('village_id', openapi.IN_QUERY, description="Village ID", type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING)
        ],
        responses={200: openapi.Response(description="Samaj list", schema=SamajSerializer(many=True)), 400: "Village ID is required"}
    )
    def get(self, request):
        village_id = request.GET.get("village_id")
        if not village_id:
            return Response({"error": "Village ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        lang = request.GET.get("lang", "en")
        samaj = Samaj.objects.filter(village__id=village_id).order_by('name')
        serializer = SamajSerializer(samaj, many=True, context={"lang": lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

class SurnameByVillageView(APIView):
    """Returns only surnames that have members in a specific village."""
    @swagger_auto_schema(
        operation_description="Get surnames present in a specific village",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING),
        ],
        responses={200: openapi.Response(description="Surnames list", schema=SurnameSerializer(many=True)), 400: "Village ID is required"}
    )
    def get(self, request):
        lang = request.GET.get("lang", "en")
        mobile_number = request.headers.get("X-Mobile-Number")

        # Validate mobile number
        if not mobile_number:
            return Response(
                {"error": "Mobile number is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Fetch login person
        login_person = Person.objects.filter(
            Q(mobile_number1=mobile_number) |
            Q(mobile_number2=mobile_number),
            is_deleted=False
        ).select_related("samaj__village").first()

        if not login_person:
            return Response(
                {"error": "Person not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if not login_person.samaj_id:
            return Response(
                {"error": "Samaj not assigned to this user"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Filter only login user's samaj
        person_filter = Q(
            samaj_id=login_person.samaj_id,
            is_deleted=False,
            flag_show=True
        )

        surname_ids = (
            Person.objects
            .filter(person_filter)
            .values_list("surname_id", flat=True)
            .distinct()
        )

        surnames = Surname.objects.filter(id__in=surname_ids).order_by("name")
        serializer = SurnameSerializer(surnames, many=True, context={"lang": lang})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class V4LoginAPI(APIView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_description="V4 Login API for members",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['mobile_number'],
            properties={
                'mobile_number': openapi.Schema(type=openapi.TYPE_STRING),
                'lang': openapi.Schema(type=openapi.TYPE_STRING, default='en'),
                'player_id': openapi.Schema(type=openapi.TYPE_STRING),
                'is_ios_platform': openapi.Schema(type=openapi.TYPE_BOOLEAN, default=False)
            }
        ),
        responses={200: "Success Login", 400: "Mobile number missing", 404: "Person not found"}
    )
    def post(self, request):
        mobile_number = request.data.get("mobile_number")
        lang = request.data.get("lang", "en")
        player_id = request.data.get("player_id", "")
        is_ios_platform = request.data.get("is_ios_platform", False)

        if not mobile_number:
            error_message = (
                "મોબાઈલ નંબર જરૂરી છે" if lang == "guj" else "Mobile number is required"
            )
            return Response({"message": error_message}, status=status.HTTP_400_BAD_REQUEST)

        # DEMO_MOBILE_NUMBER = "1111111111"
        # is_demo = mobile_number == DEMO_MOBILE_NUMBER

        try:
        #     if is_demo:
        #         person = Person.objects.get(
        #             Q(mobile_number1=mobile_number) | Q(mobile_number2=mobile_number),
        #             is_deleted=False,
        #         )
        #     else:
                # is_demo_setting = mobile_number in getattr(settings, "DEMO_MOBILE_NUMBERS", [])
                # if is_demo_setting:
                #     person = DemoPerson.objects.get(
                #         Q(mobile_number1=mobile_number) | Q(mobile_number2=mobile_number),
                #         is_deleted=False,
                #     )
                #     is_demo = True
                # else:
            person = Person.objects.get(
                Q(mobile_number1=mobile_number) | Q(mobile_number2=mobile_number),
                is_deleted=False,
            )
        except (Person.DoesNotExist, Person.DoesNotExist):
            error_message = "સભ્ય નોંધાયેલ નથી" if lang == "guj" else "Person not found"
            return Response({"message": error_message}, status=status.HTTP_404_NOT_FOUND)

        available_platform = "Ios" if is_ios_platform == True else "Android"

        if player_id :
            try:
                player_person = PersonPlayerId.objects.get(player_id=player_id)
                if player_person:
                    player_person.person = person
                    player_person.platform = available_platform
                    player_person.save()
            except Exception:
                PersonPlayerId.objects.create(
                    person=person,
                    player_id=player_id,
                    platform=available_platform,
                )

        serializer = PersonV4Serializer(
            person, context={"lang": lang, "person_id": person.id}
        )
        print("Person serializer data:", serializer.data)
        admin_data = getadmincontact(
            serializer.data.get("flag_show"), lang, serializer.data.get("surname")
        )
        
        admin_data["person"] = serializer.data
        
        # Add samaj data and referral code
        # admin_data["referral_code"] = ""
        # admin_data["samaj_list"] = []
        # if person.samaj.village:
        #     samaj_in_village = person.samaj.village.samaj_list.all()
        #     admin_data["samaj_list"] = SamajSerializer(samaj_in_village, many=True, context={"lang": lang}).data
        #     print(" samaj_in_village: ", admin_data["samaj_list"])
        #     # Prioritize the person's own samaj referral code
        #     if person.samaj and person.samaj.referral_code:
        #         admin_data["referral_code"] = person.samaj.referral_code
        #         print("Referral code from person's samaj: ", admin_data["referral_code"])
        #     # Fallback to first samaj in village for backward compatibility
        #     elif samaj_in_village.exists() and samaj_in_village.first().referral_code:
        #         admin_data["referral_code"] = samaj_in_village.first().referral_code
        #         print("Referral code from first samaj in village: ", admin_data["referral_code"])
        # print("Admin data before pending count:", admin_data)
        admin_user_id = serializer.data.get("id")
        if admin_user_id:
            # if is_demo:
            #     pendingdata_count = 0
            # else:
            try:
                person_obj = Person.objects.get(pk=admin_user_id, is_deleted=False)
                print("Person object for pending data count:", type(person_obj))
                if person_obj.is_admin or person_obj.is_super_admin:
                    if person_obj.is_super_admin:
                        pending_users = Person.objects.filter(
                            flag_show=False, is_deleted=False
                        )
                        print("Pending users for super admin:", pending_users)
                    else:
                        pending_users = Person.objects.filter(
                            flag_show=False, 
                            samaj=person_obj.samaj,
                            surname=person_obj.surname,
                            is_deleted=False
                        ).exclude(id=person_obj.surname.top_member if person_obj.surname else None)
                    pendingdata_count = pending_users.count()
                    print("Pending data count:", pendingdata_count)
                else:
                    pendingdata_count = 0
            except Person.DoesNotExist:
                pendingdata_count = 0
            
            response_data = {"pending-data": pendingdata_count}
            response_data.update(admin_data)
            return Response(response_data, status=status.HTTP_200_OK)
            
        return Response(admin_data, status=status.HTTP_200_OK)

class AllVillageListView(APIView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_description="Get list of all villages for initial registration selection",
        responses={200: openapi.Response(
            description="List of villages",
            schema=VillageSerializer(many=True)
        )}
    )
    def get(self, request):
        lang = request.GET.get("lang", "en")
        villages = Village.objects.filter(
            is_active=True, 
            taluka__is_active=True, 
            taluka__district__is_active=True
        ).order_by('name')
        serializer = VillageSerializer(villages, many=True, context={'lang': lang})
        return Response(serializer.data, status=status.HTTP_200_OK)


class VillageTalukaView(APIView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_description="Get the parent Taluka for a village",
        responses={200: openapi.Response(
            description="Parent Taluka details",
            schema=TalukaSerializer
        ), 404: "Village not found"}
    )
    def get(self, request, village_id):
        try:
            village = Village.objects.select_related('taluka', 'taluka__district').get(pk=village_id)
            if not village.is_active or not village.taluka.is_active or not village.taluka.district.is_active:
                return Response({"message": "Location deactivated. Please contact admin."}, status=status.HTTP_403_FORBIDDEN)
            serializer = TalukaSerializer(village.taluka, context={'lang': request.GET.get("lang", "en")})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Village.DoesNotExist:
            return Response({"error": "Village not found"}, status=status.HTTP_404_NOT_FOUND)

class TalukaDistrictView(APIView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_description="Get the parent District for a taluka",
        responses={200: openapi.Response(
            description="Parent District details",
            schema=DistrictSerializer
        ), 404: "Taluka not found"}
    )
    def get(self, request, taluka_id):
        try:
            taluka = Taluka.objects.select_related('district').get(pk=taluka_id)
            if not taluka.is_active or not taluka.district.is_active:
                return Response({"message": "Location deactivated. Please contact admin."}, status=status.HTTP_403_FORBIDDEN)
            serializer = DistrictSerializer(taluka.district, context={'lang': request.GET.get("lang", "en")})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Taluka.DoesNotExist:
            return Response({"error": "Taluka not found"}, status=status.HTTP_404_NOT_FOUND)
        

class V4RelationtreeAPIView(APIView):

    def get(self, request):
        lang = request.GET.get("lang", "en")
        person_id = request.GET.get("person_id")
        mobile_number = request.headers.get("X-Mobile-Number")
        login_village_id = None

        if not mobile_number:
            return Response(
                {"error": "Mobile number is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if mobile_number:
            login_person = Person.objects.filter(
                Q(mobile_number1=mobile_number) |
                Q(mobile_number2=mobile_number),
                is_deleted=False
            ).select_related("samaj__village").first()

            if login_person and login_person.samaj and login_person.samaj.village_id:
                login_village_id = login_person.samaj.village_id

            if not login_village_id:
                return Response(
                    {"error": "Login person's village information is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        try:
            person = Person.objects.get(id=person_id, is_deleted=False)
            surname = person.surname.id
            surname_topmember = Surname.objects.get(id=surname)
            topmember = surname_topmember.top_member

            # Initialize relations with the first query
            relations = ParentChildRelation.objects.filter(child_id=person_id)
            parent_data_id = {
                person_id
            }  # To keep track of already processed parent ids

            while relations:
                new_relations = []
                for relation in relations:
                    parent_id = relation.parent.id
                    if parent_id == topmember:
                        break
                    if parent_id not in parent_data_id:
                        parent_data_id.add(parent_id)
                        new_relations.extend(
                            ParentChildRelation.objects.filter(
                                child_id=parent_id, is_deleted=False
                            )
                        )
                relations = new_relations
            
            person_data_queryset = (
                Person.objects.filter(
                    surname__id=surname, flag_show=True, is_deleted=False
                )
                .exclude(id__in=parent_data_id)
                .annotate(
                    translated_first_name_annotated=Case(
                        # Gujarati translated name exists
                        When(
                            Q(
                                translateperson__first_name__isnull=False,
                                translateperson__language=lang,
                            ) &
                            ~Q(samaj__village_id=login_village_id),   
                            then=Concat(
                                F("translateperson__first_name"),
                                Value(" ("),
                                F("samaj__village__name"),
                                Value(")"),
                                output_field=CharField(),
                            ),
                        ),
                        # English name outside village
                        When(
                            ~Q(samaj__village_id=login_village_id),
                            then=Concat(
                                F("first_name"),
                                Value(" ("),
                                F("samaj__village__name"),
                                Value(")"),
                                output_field=CharField(),
                            ),
                        ),
                        # Default (same village)
                        default=Case(
                            When(
                                Q(
                                    translateperson__first_name__isnull=False,
                                    translateperson__language=lang,
                                ),
                                then=F("translateperson__first_name"),
                            ),
                            default=F("first_name"),
                        ),
                        output_field=CharField(),
                    ),
                    translated_middle_name_annotated=Case(
                        When(
                            Q(
                                translateperson__middle_name__isnull=False,
                                translateperson__language=lang,
                            ),
                            then=F("translateperson__middle_name"),
                        ),
                        default=F("middle_name"),
                        output_field=CharField(),
                    )
                )
                .order_by("first_name")
                .prefetch_related("translateperson")
            )

            # Manual serialization for specific format
            data = []
            for p in person_data_queryset:
                data.append({
                    "id": p.id,
                    "date_of_birth": p.date_of_birth,
                    "profile": p.profile.url if p.profile else os.getenv("DEFAULT_PROFILE_PATH"),
                    "thumb_profile": p.thumb_profile.url if p.thumb_profile else os.getenv("DEFAULT_PROFILE_PATH"),
                    "mobile_number1": p.mobile_number1,
                    "mobile_number2": p.mobile_number2,
                    "out_of_country": p.out_of_country.name if p.out_of_country else "", # Minimal for relation-tree
                    "flag_show": p.flag_show,
                    "emoji": p.emoji if hasattr(p, 'emoji') else "",
                    "translated_first_name": p.translated_first_name_annotated,
                    "translated_middle_name": p.translated_middle_name_annotated,
                })

            return Response({"data": data})

        except Person.DoesNotExist:
            return Response(
                {"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Surname.DoesNotExist:
            return Response(
                {"error": "Surname not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class V4ParentChildRelationDetailView(APIView):
    def post(self, request):
        serializer = ParentChildRelationSerializer(data=request.data)
        if serializer.is_valid():
            parent_id = serializer.validated_data.get("parent_id")
            child_id = serializer.validated_data.get("child_id")
            try:
                existing_relation = ParentChildRelation.objects.get(
                    child_id=child_id, is_deleted=False
                )
                existing_relation.parent_id = parent_id
                existing_relation.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except ParentChildRelation.DoesNotExist:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, surnameid=None):
        if surnameid:
            try:
                surnameid = int(surnameid)

            except ValueError:
                return Response(
                    {"error": "Invalid surname ID"}, status=status.HTTP_400_BAD_REQUEST
                )
            lang = request.GET.get("lang", "en")
            mobile_number = request.headers.get("X-Mobile-Number")
            login_village_id = None

            if not mobile_number:
                return Response(
                    {"error": "Mobile number is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if mobile_number:
                login_person = Person.objects.filter(
                    Q(mobile_number1=mobile_number) |
                    Q(mobile_number2=mobile_number),
                    is_deleted=False
                ).select_related("samaj__village").first()

                if login_person and login_person.samaj and login_person.samaj.village_id:
                    login_village_id = login_person.samaj.village_id

                if not login_village_id:
                    return Response(
                        {"error": "Login person's village information is required"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Query
            queryset = (
                Person.objects.filter(surname__id=surnameid, is_deleted=False)
                .order_by("date_of_birth")
                .annotate(
                    translated_first_name=Case(

                        # Gujarati translated name exists
                        When(
                            Q(
                                translateperson__first_name__isnull=False,
                                translateperson__language=lang,
                            ) &
                            ~Q(samaj__village_id=login_village_id),   
                            then=Concat(
                                F("translateperson__first_name"),
                                Value(" ("),
                                F("samaj__village__name"),
                                Value(")"),
                                output_field=CharField(),
                            ),
                        ),

                        # English name outside village
                        When(
                            ~Q(samaj__village_id=login_village_id),
                            then=Concat(
                                F("first_name"),
                                Value(" ("),
                                F("samaj__village__name"),
                                Value(")"),
                                output_field=CharField(),
                            ),
                        ),

                        # Default (same village)
                        default=Case(
                            When(
                                Q(
                                    translateperson__first_name__isnull=False,
                                    translateperson__language=lang,
                                ),
                                then=F("translateperson__first_name"),
                            ),
                            default=F("first_name"),
                        ),

                        output_field=CharField(),
                    ),
                    translated_middle_name=Case(
                        When(
                            Q(
                                translateperson__middle_name__isnull=False,
                                translateperson__language=lang,
                            ),
                            then=F("translateperson__middle_name"),
                        ),
                        default=F("middle_name"),
                    ),
                    village_name=F("samaj__village__name"),
                    samaj_name=F("samaj__name"),
                )
                .select_related("surname")
                .prefetch_related("translateperson")
            )

            # Execute the query and fetch results
            results = list(
                queryset.values(
                    "id",
                    "translated_first_name",
                    "translated_middle_name",
                    "date_of_birth",
                    "profile",
                    "thumb_profile",
                    "mobile_number1",
                    "mobile_number2",
                    "out_of_country",
                    "flag_show",
                    "village_name",
                    "samaj_name",
                    "emoji",
                )
            )

            total_count = len(results)
            relation_data = (
                ParentChildRelation.objects.filter(
                    Q(parent__surname__id=surnameid)
                    and Q(child__surname__id=surnameid),
                    is_deleted=False,
                )
                .select_related("parent", "child")
                .order_by("parent__date_of_birth", "child__date_of_birth")
            )
            data2 = []
            if relation_data.exists():
                data = GetTreeRelationSerializer(relation_data, many=True).data
                if len(data) > 0:
                    surname_data = Surname.objects.filter(Q(id=int(surnameid)))
                    if surname_data.exists():
                        surname_data = surname_data.first()
                        top_member = int(
                            GetSurnameSerializer(surname_data).data.get("top_member", 0)
                        )
                        filtered_surname_results = filter(
                            lambda person: person["id"] == top_member, results
                        )
                        surname_relations = next(filtered_surname_results, None)
                        default_path = os.path.join(
                            settings.MEDIA_ROOT,
                            os.getenv("DEFAULT_PROFILE_PATH_WITHOUT_MEDIA"),
                        )
                        for j in data:
                            filtered_parent_results = filter(
                                lambda person: person["id"] == j["parent"], results
                            )
                            parent_relations = next(filtered_parent_results, None)
                            if parent_relations:
                                if (
                                    parent_relations["profile"] != "null"
                                    and parent_relations["profile"] != ""
                                ):
                                    file_path = os.path.join(
                                        settings.MEDIA_ROOT, parent_relations["profile"]
                                    )
                                    if not os.path.exists(file_path):
                                        parent_relations["profile"] = default_path
                                else:
                                    parent_relations["profile"] = default_path
                                if (
                                    parent_relations["thumb_profile"] != "null"
                                    and parent_relations["thumb_profile"] != ""
                                ):
                                    file_path = os.path.join(
                                        settings.MEDIA_ROOT,
                                        parent_relations["thumb_profile"],
                                    )
                                    if not os.path.exists(file_path):
                                        parent_relations["thumb_profile"] = default_path
                                else:
                                    parent_relations["thumb_profile"] = default_path
                            filtered_child_results = filter(
                                lambda person: person["id"] == j["child"], results
                            )
                            child_relations = next(filtered_child_results, None)
                            if child_relations:
                                if (
                                    child_relations["profile"] != "null"
                                    and child_relations["profile"] != ""
                                ):
                                    file_path = os.path.join(
                                        settings.MEDIA_ROOT, child_relations["profile"]
                                    )
                                    if not os.path.exists(file_path):
                                        child_relations["profile"] = default_path
                                else:
                                    child_relations["profile"] = default_path
                                if (
                                    child_relations["thumb_profile"] != "null"
                                    and child_relations["thumb_profile"] != ""
                                ):
                                    file_path = os.path.join(
                                        settings.MEDIA_ROOT,
                                        child_relations["thumb_profile"],
                                    )
                                    if not os.path.exists(file_path):
                                        child_relations["thumb_profile"] = default_path
                                else:
                                    child_relations["thumb_profile"] = default_path
                            if child_relations["flag_show"] == True:
                                j["child"] = child_relations
                                j["parent"] = parent_relations
                                parent = j.get("parent")
                                flag_show = None
                                if parent and isinstance(parent, dict):
                                    flag_show = parent.get("flag_show")
                                if flag_show is not True:
                                    j["parent"] = surname_relations
                                data2.append(j)
            return Response(
                {"total_count": total_count, "data": data2}, status=status.HTTP_200_OK
            )
        else:
            return Response({"total_count": 0, "data": []}, status=status.HTTP_200_OK)

    def get_parent_child_relation(self, param, dictionary, lang):
        parent_child_relation = ParentChildRelation.objects.filter(
            Q(parent_id=param) | Q(child_id=param), is_deleted=False
        )
        if parent_child_relation:
            serializer = GetParentChildRelationSerializer(
                parent_child_relation, many=True, context={"lang": lang}
            )
            for child in serializer.data:
                tmp = None
                if len(dictionary) > 0:
                    for data in dictionary:
                        if int(child.get("child", None).get("id", None)) == int(
                            data.get("child", None).get("id", None)
                        ) and int(data.get("parent", None).get("id", None)) == int(
                            child.get("parent", None).get("id", None)
                        ):
                            tmp = data
                            break
                if not tmp:
                    dictionary.append(child)
                    self.get_parent_child_relation(
                        int(child.get("parent", None).get("id", None)), dictionary, lang
                    )
                    self.get_parent_child_relation(
                        int(child.get("child", None).get("id", None)), dictionary, lang
                    )

    def put(self, request, pk=None):
        created_user_id = request.data.get("created_user")
        lang = request.data.get("lang")
        if not created_user_id:
            return Response(
                {"error": "Admin Data not provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            created_user = Person.objects.get(id=created_user_id, is_deleted=False)
        except Person.DoesNotExist:
            return Response(
                {"error": "Admin memeber not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if not (created_user.is_admin or created_user.is_super_admin):
            return Response(
                {"error": "Permission denied: Only admins can edit this relation"},
                status=status.HTTP_403_FORBIDDEN,
            )
        parent_id = request.data.get("parent_id")
        if not parent_id:
            return Response(
                {"error": "Parent Data not provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            parent = Person.objects.get(id=parent_id, is_deleted=False)
        except Person.DoesNotExist:
            return Response(
                {"error": "Parent not found for this member."},
                status=status.HTTP_404_NOT_FOUND,
            )
        child_id = request.data.get("child_id")
        if not child_id:
            return Response(
                {"error": "Child Data not provided"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            child = Person.objects.get(id=child_id, is_deleted=False)
            if child:
                child.middle_name = parent.first_name
                child.save()
            try:
                parent_translate = TranslatePerson.objects.get(
                    person_id=parent_id, is_deleted=False
                )
                translate = TranslatePerson.objects.get(
                    person_id=child.id, is_deleted=False
                )
                if translate:
                    translate.middle_name = parent_translate.first_name
                    translate.save()
            except:
                pass
        except Person.DoesNotExist:
            return Response(
                {"error": "Child not found"}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            relation = ParentChildRelation.objects.get(child=child, is_deleted=False)
            if parent != child:
                try:
                    relation.parent = parent
                    relation.save()
                    return Response(
                        {
                            "message": "Your child is successfully moved under the "
                            + parent.first_name
                        },
                        status=status.HTTP_200_OK,
                    )
                except:
                    return Response(
                        {"message": "something is wrong"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
        except:
            pass
        return Response(
            {"message": "something is wrong"}, status=status.HTTP_403_FORBIDDEN
        )
    
class V4PersonDetailView(APIView):
    authentication_classes = []
    def get(self, request, pk):
        try:
            person = Person.objects.get(id=pk)
            if person:
                lang = request.GET.get('lang', 'en')
                person = PersonGetSerializer(person, context={'lang': lang}).data
                person['child'] = []
                person['parent'] = {}
                person['brother'] = []
                child_data = ParentChildRelation.objects.filter(parent=int(person["id"]))
                if child_data.exists():
                    child_data = GetParentChildRelationSerializer(child_data, many=True, context={'lang': lang}).data
                    for child in child_data:
                        person['child'].append(child.get("child"))
                parent_data = ParentChildRelation.objects.filter(child=int(person["id"])).first()
                if parent_data:
                    parent_data = GetParentChildRelationSerializer(parent_data, context={'lang': lang}).data
                    person['parent'] = parent_data.get("parent")
                    brother_data = ParentChildRelation.objects.filter(parent=int(parent_data.get("parent").get("id", 0)))
                    if brother_data.exists():
                        brother_data = GetParentChildRelationSerializer(brother_data, many=True, context={'lang': lang}).data
                        for brother in brother_data:
                            if int(person["id"]) != int(brother["child"]["id"]) :
                                person['brother'].append(brother.get("child"))
                return Response(person, status=status.HTTP_200_OK)
        except Person.DoesNotExist:
            return Response({'error': 'Person not found'}, status=status.HTTP_404_NOT_FOUND)
        
    def post(self, request):
        surname = request.data.get('surname', 0)
        persons_surname_wise = Surname.objects.filter(Q(id=int(surname))).first()
        father = request.data.get('father', 0)        
        top_member = 0
        if persons_surname_wise: 
            top_member = int(GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0))
            if father == 0 :
                father = top_member
        children = request.data.get('child', [])
        first_name = request.data.get('first_name')
        middle_name = request.data.get('middle_name')
        address = request.data.get('address')
        out_of_address = request.data.get('out_of_address')
        lang = request.data.get('lang', 'en')
        date_of_birth = request.data.get('date_of_birth')
        blood_group = request.data.get('blood_group', 1)
        city = request.data.get('city')
        state = request.data.get('state')
        out_of_country = request.data.get('out_of_country', 1)
        if (int(out_of_country) == 0) :
            out_of_country = 1
        flag_show = request.data.get('flag_show')
        mobile_number1 = request.data.get('mobile_number1')
        mobile_number2 = request.data.get('mobile_number2')
        samaj_id = request.data.get('samaj')
        status_name = request.data.get('status')
        is_admin = request.data.get('is_admin')
        is_registered_directly = request.data.get('is_registered_directly')
        person_data = {
            'first_name': first_name,
            'middle_name': middle_name,
            'address': address,
            'out_of_address': out_of_address,
            'date_of_birth': date_of_birth,
            'blood_group': blood_group,
            'city': city,
            'state': state,
            'out_of_country': out_of_country,
            'flag_show': flag_show,
            'mobile_number1': mobile_number1,
            'mobile_number2': mobile_number2,
            'status': status_name,
            'surname': surname,
            'is_admin': is_admin,
            'is_registered_directly': is_registered_directly
        }
        serializer = PersonV4Serializer(data=person_data)
        if serializer.is_valid():
            if len(children) > 0 :
                children_exist = ParentChildRelation.objects.filter(child__in=children)
                if children_exist.exclude(parent=top_member).exists():
                    return JsonResponse({'message': 'Children already exist'}, status=400)
                children_exist.filter(parent=top_member).delete()
            persons = serializer.save()
            try:
                if not first_name:
                    raise ValueError("first_name is required")
                user, user_created = User.objects.get_or_create(username=first_name)
                if user_created:
                    user.set_password(''.join(choices(string.ascii_letters + string.digits, k=12)))
                user.save()
                if user_created:
                    print(f"New user created: {user.username}")
                else:
                    print(f"User updated (username): {user.username}")
            except IntegrityError as e:
                # Handle potential duplicate username or other database integrity errors
                print(f"IntegrityError encountered: {e}")
            parent_serializer = ParentChildRelationSerializer(data={
                                'parent': father, 
                                'child': persons.id,
                                'created_user': persons.id
                            })
            if parent_serializer.is_valid():
                parent_serializer.save()
            for child in children :
                child_serializer = ParentChildRelationSerializer(data={
                                'child': child, 
                                'parent': persons.id,
                                'created_user': persons.id
                            })
                if child_serializer.is_valid():
                    child_serializer.save()
            if (lang != "en") :   
                person_translate_data = {
                    'first_name': first_name, 
                    'person_id': persons.id,
                    'middle_name': middle_name,
                    'address': address,
                    'out_of_address':out_of_address,

                    'language': lang
                }
                person_translate_serializer = TranslatePersonSerializer(data=person_translate_data)
                if person_translate_serializer.is_valid():
                    person_translate_serializer.save()
            return Response(PersonGetSerializer(persons, context={'lang': lang}).data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, pk):
        person = get_object_or_404(Person, pk=pk)
        if not person:
            return JsonResponse({'message': 'Person not found'}, status=status.HTTP_400_BAD_REQUEST)
        surname = request.data.get('surname', 0)
        persons_surname_wise = Surname.objects.filter(Q(id=int(surname))).first()
        father = request.data.get('father', 0) 
        top_member = 0
        if persons_surname_wise: 
            top_member = int(GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0))
            if father == 0:
                father = top_member
        children = request.data.get('child', [])
        first_name = request.data.get('first_name')
        middle_name = request.data.get('middle_name')
        address = request.data.get('address')
        out_of_address = request.data.get('out_of_address')
        lang = request.data.get('lang', 'en')
        date_of_birth = request.data.get('date_of_birth')
        blood_group = request.data.get('blood_group', 1)
        city = request.data.get('city')
        state = request.data.get('state')
        out_of_country = request.data.get('out_of_country', 1)
        if (int(out_of_country) == 0) :
            out_of_country = 1
        flag_show = request.data.get('flag_show')
        mobile_number1 = request.data.get('mobile_number1')
        mobile_number2 = request.data.get('mobile_number2')
        status_name = request.data.get('status')
        is_admin = request.data.get('is_admin')
        is_registered_directly = request.data.get('is_registered_directly')
        person_data = {
            'first_name' : person.first_name if lang == 'en' else first_name,
            'middle_name' : person.middle_name if lang == 'en' else middle_name,
            'address' : person.address if lang == 'en' else address,
            'out_of_address': out_of_address,
            'date_of_birth': date_of_birth,
            'blood_group': blood_group,
            'city': city,
            'state': state,
            'out_of_country': out_of_country,
            'flag_show': flag_show,
            'mobile_number1': mobile_number1,
            'mobile_number2': mobile_number2,
            'status': status_name,
            'surname': surname,
            'is_admin': is_admin,
            'is_registered_directly': is_registered_directly
        }

        ignore_fields = ['update_field_message', 'id', 'flag_show', 'is_admin', 'is_registered_directly']
        update_field_message = []
        for field, new_value in person_data.items():
            if field in ignore_fields:
                continue
            old_value = getattr(person, field, None)

            if hasattr(old_value, 'id'):
                old_value = old_value.id

            if old_value != new_value:
                update_field_message.append({
                    'field': field,
                    'previous': old_value,
                    'new': new_value
                })

        if update_field_message:
            person.update_field_message = str(update_field_message)
            
        serializer = PersonV4Serializer(person, data=person_data, context={'person_id': person.id})
        if serializer.is_valid():
            if len(children) > 0:
                children_exist = ParentChildRelation.objects.filter(child__in=children)
                if children_exist.exclude(parent=top_member).exclude(parent=person.id).exists():
                    return JsonResponse({'message': 'Children already exist'}, status=400)
            persons = serializer.save()

            father_data = ParentChildRelation.objects.filter(child=persons.id)
            data = { 
                    'parent': father, 
                    'child': persons.id,
                    'created_user': persons.id
                }
            father_data_serializer = None
            if father_data.exists() :
                father_data = father_data.first()
                father_data_serializer = ParentChildRelationSerializer(father_data, data=data)
            else :
                father_data_serializer = ParentChildRelationSerializer(data=data)
            if father_data_serializer.is_valid():
                father_data_serializer.save()
            for child in children:
                child_data = ParentChildRelation.objects.filter(child=child)
                data = { 
                    'child': child, 
                    'parent': persons.id,
                    'created_user': persons.id
                }
                child_data_serializer = None
                if child_data.exists() :
                    child_data = child_data.first()
                    child_data_serializer = ParentChildRelationSerializer(child_data, data=data)
                else :
                    child_data_serializer = ParentChildRelationSerializer(data=data)
                if child_data_serializer.is_valid():
                    child_data_serializer.save()
            if len(children) > 0:       
                remove_child_person = ParentChildRelation.objects.filter(parent=persons.id).exclude(child__in=children)
                if remove_child_person.exists():
                    for child in remove_child_person:
                        child.parent_id = int(top_member)
                        child.save()
            if (lang != "en"):
                lang_data = TranslatePerson.objects.filter(person_id=persons.id).filter(language=lang)
                if lang_data.exists() :
                    lang_data = lang_data.first()
                    person_translate_data = {
                        'first_name': first_name,
                        'middle_name': middle_name,
                        'address': address,
                        'out_of_address':out_of_address,
                        'language': lang
                    }
                    person_translate_serializer = TranslatePersonSerializer(lang_data, data=person_translate_data)
                    if person_translate_serializer.is_valid():
                        person_translate_serializer.save()
            return Response({
                "person": PersonGetSerializer(persons, context={'lang': lang}).data
            }, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        person = get_object_or_404(Person, pk=pk)
        try:
            person.delete()
            return Response({"message": "Person record deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({"message": f"Failed to delete the person record: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class V4AdminAccess(APIView):
    def get(self, request):
        lang = request.GET.get("lang", "en")
        admin_user_id = request.GET.get("admin_user_id")
        if not admin_user_id:
            if lang == "guj":
                return Response(
                    {"message": "એડમીન મળી રહીયો નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": "Missing Admin User in request data"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        try:
            admin_person = Person.objects.get(pk=admin_user_id, is_deleted=False)
        except Person.DoesNotExist:
            if lang == "en":
                return Response(
                    {"message": f"Admin Person not found"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": f"એડમિન વ્યક્તિ મળી રહી નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        if not admin_person.is_super_admin:
            if lang == "en":
                return Response(
                    {
                        "message": "User does not have permission for create admin member"
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": "તમારી પાસે એડમિન સભ્ય બનાવવાની પરવાનગી નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        admin_data = Person.objects.filter(
            Q(is_admin=True) or Q(is_super_admin=True), is_deleted=False
        )
        serializer = PersonGetSerializer(admin_data, context={"lang": lang}, many=True)
        return Response({"admin-data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        lang = request.data.get("lang", "en")
        mobile = request.data.get("mobile")
        admin_user_id = request.data.get("admin_user_id")
        if not admin_user_id:
            if lang == "guj":
                return Response(
                    {"message": "એડમીન મળી રહીયો નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": "Missing Admin User in request data"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        try:
            admin_person = Person.objects.get(pk=admin_user_id, is_deleted=False)
        except Person.DoesNotExist:
            if lang == "en":
                return Response(
                    {"message": f"Admin Person not found"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": f"એડમિન વ્યક્તિ મળી રહી નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        if not admin_person.is_super_admin:
            if lang == "en":
                return Response(
                    {
                        "message": "User does not have permission for create admin member"
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": "તમારી પાસે એડમિન સભ્ય બનાવવાની પરવાનગી નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        admin_access = Person.objects.filter(
            Q(mobile_number1__in=mobile) or Q(mobile_number2__in=mobile),
            is_deleted=False,
        )

        if admin_access:
            for admin in admin_access:
                if admin.flag_show == True:
                    mobile_last = admin.mobile_number1[-4:]
                    new_password = mobile_last
                    admin.is_admin = True
                    admin.password = new_password
                    admin.save()

            admin_access = admin_access.exclude(flag_show=True)
            serializer = PersonV4Serializer(admin_access, many=True)
            if admin_access.exists():
                error_message = ""
                for admin in serializer.data:
                    error_message += (
                        f"{admin.get('mobile_number1')} {admin.get('mobile_number2')} "
                    )
                if lang == "guj":
                    error_message += f"સભ્ય ની ચકાસણી અને અપડૅટ કરો"
                else:
                    error_message += f"Verify and update the member"
                return Response({"message": error_message})
            if lang == "guj":
                return Response(
                    {"message": "સફળતાપૂર્વક એડમિન બનાવ્યું"}, status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {"message": "Succesfully admin Created"}, status=status.HTTP_200_OK
                )
        else:
            if lang == "guj":
                return Response(
                    {"message": "સભ્ય નોંધાયેલ નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": "Member is Not registerd"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

    def delete(self, request):
        lang = request.data.get("lang", "en")
        mobile = request.data.get("mobile")
        admin_user_id = request.data.get("admin_user_id")
        if not admin_user_id:
            if lang == "guj":
                return Response(
                    {"message": "એડમીન મળી રહીયો નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": "Missing Admin User in request data"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        try:
            admin_person = Person.objects.get(pk=admin_user_id, is_deleted=False)
        except Person.DoesNotExist:
            if lang == "en":
                return Response(
                    {"message": f"Admin Person not found"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": f"એડમિન વ્યક્તિ મળી રહી નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        if not admin_person.is_super_admin:
            if lang == "en":
                return Response(
                    {
                        "message": "User does not have permission for to remove admin member"
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": "તમારી પાસે એડમિન સભ્ય કાઢવાની પરવાનગી નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        admin_access = Person.objects.filter(
            Q(mobile_number1__in=mobile) or Q(mobile_number2__in=mobile),
            is_admin=True,
            is_deleted=False,
        )
        if admin_access:
            for admin in admin_access:
                if admin.flag_show == True:
                    admin.is_admin = False
                    admin.password = ""
                    admin.save()

        if lang == "guj":
            return Response(
                {"message": "સફળતાપૂર્વક એડમિન કાઢી નાખ્યું"}, status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"message": "Succesfully admin remove"}, status=status.HTTP_200_OK
            )

class V4AdminPersons(APIView):
    def get(self, request):
        person_id = request.GET.get("person_id")
        if not person_id:
            return Response(
                {"message": "Please Enter a Person ID"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            person = Person.objects.get(id=person_id, is_deleted=False)
        except Person.DoesNotExist:
            return Response(
                {"message": "Person Not Found"}, status=status.HTTP_404_NOT_FOUND
            )

        lang = request.GET.get("lang", "en")
        # ===== Permission Based Admin List =====

        if person.is_super_admin:
            # Super admin → all admins
            admin_persons = Person.objects.filter(
                Q(is_admin=True) | Q(is_super_admin=True),
                is_deleted=False,
            )

        elif person.is_admin:
            # Admin → only same village admins
            if person.samaj and person.samaj.village_id:
                admin_persons = Person.objects.filter(
                    Q(is_admin=True) | Q(is_super_admin=True),
                    samaj__village_id=person.samaj.village_id,
                    is_deleted=False,
                )
            else:
                admin_persons = Person.objects.none()

        else:
            # Non-admin cannot access
            return Response(
                {"message": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        admin_persons = (
            admin_persons
            .exclude(id=person.id)
            .select_related("surname", "samaj__village")
            .order_by("first_name")
        )

        surname_dict = {}
        for admin_person in admin_persons:
            surname_name = (
                admin_person.surname.name if admin_person.surname else "Unknown"
            )
            if surname_name not in surname_dict:
                surname_dict[surname_name] = []
            surname_dict[surname_name].append(admin_person)

        grouped_data = []
        for surname, persons in surname_dict.items():
            surname_serializer = GetSurnameSerializerdata(
                persons[0].surname, context={"lang": lang}
            )
            person_serializer = PersonDataAdminSerializer(
                persons, many=True, context={"lang": lang}
            )
            grouped_data.append(
                {"surname": surname_serializer.data, "persons": person_serializer.data}
            )

        return Response({"data": grouped_data}, status=status.HTTP_200_OK)

    def post(self, request):
        surname = request.data.get("surname")
        lang = request.data.get("lang", "en")
        if surname is None:

            if lang == "guj":
                return JsonResponse(
                    {"message": "અટક જરૂરી છે", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                return JsonResponse(
                    {"message": "Surname ID is required", "data": []},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        surname_data = Surname.objects.filter(Q(id=int(surname)))
        if surname_data.exists():
            surname_data = surname_data.first()
            top_member = int(
                GetSurnameSerializer(surname_data).data.get("top_member", 0)
            )
            persons = (
                Person.objects.filter(
                    Q(surname__id=int(surname)),
                    is_admin=False,
                    is_super_admin=False,
                    flag_show=True,
                    mobile_number1__isnull=False,
                )
                .exclude(id=top_member)
                .exclude(mobile_number1=["", None])
                .order_by("first_name")
            )
            if persons.exists():
                serializer = PersonGetSerializer(
                    persons, many=True, context={"lang": lang}
                )
                if len(serializer.data) > 0:
                    data = sorted(
                        serializer.data,
                        key=lambda x: (x["first_name"], x["middle_name"], x["surname"]),
                    )
                    return JsonResponse({"data": data})
        return JsonResponse({"data": []}, status=status.HTTP_200_OK)

    def put(self, request):
        admin_user_id = request.data.get("admin_user_id")
        lang = request.data.get("lang", "en")
        password = request.data.get("password")

        # Ensure admin_user_id is provided
        if not admin_user_id:
            return Response(
                {"message": "admin_user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not password:
            return Response(
                {"message": "new_password is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            person = Person.objects.get(id=admin_user_id, is_deleted=False)
            if person:
                person.password = password
                person.save()
            message = (
                "પાસવર્ડ સફળતાપૂર્વક બદલાઈ ગયું છે"
                if lang == "guj"
                else "Password Changed Successfully"
            )
            return Response({"message": message}, status=status.HTTP_200_OK)
        except Person.DoesNotExist:
            message = "સભ્ય મળ્યો નથી" if lang == "guj" else "Person not found"
            return Response({"message": message}, status=status.HTTP_404_NOT_FOUND)


class V4AdminPersonDetailView(APIView):
    authentication_classes = []
    def get(self, request, pk, admin_uid):
        admin_user_id = admin_uid
        if not admin_user_id:
            return Response({'message': 'Missing Admin User in request data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        try:
            admin_person = Person.objects.get(pk=admin_user_id)
        except Person.DoesNotExist: 
            # logger.error(f'Person with ID {admin_user_id} not found')
            return Response({'message': f'Admin Person not found'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if not admin_person.is_admin and not admin_person.is_super_admin:
            return Response({'message': 'User does not have admin access'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        try:
            person = Person.objects.get(id=pk)
            if person:
                lang = request.GET.get('lang', 'en')
                person = AdminPersonGetSerializer(person, context={'lang': lang}).data
                person['child'] = []
                person['parent'] = {}
                person['brother'] = []
                child_data = ParentChildRelation.objects.filter(parent=int(person["id"]))
                if child_data.exists():
                    child_data = GetParentChildRelationSerializer(child_data, many=True, context={'lang': lang}).data
                    for child in child_data:
                        person['child'].append(child.get("child"))
                parent_data = ParentChildRelation.objects.filter(child=int(person["id"])).first()
                if parent_data:
                    parent_data = GetParentChildRelationSerializer(parent_data, context={'lang': lang}).data
                    person['parent'] = parent_data.get("parent")
                    brother_data = ParentChildRelation.objects.filter(parent=int(parent_data.get("parent").get("id", 0)))
                    if brother_data.exists():
                        brother_data = GetParentChildRelationSerializer(brother_data, many=True, context={'lang': lang}).data
                        for brother in brother_data:
                            if int(person["id"]) != int(brother["child"]["id"]) :
                                person['brother'].append(brother.get("child"))
                return Response(person, status=status.HTTP_200_OK)
        except Person.DoesNotExist:
            return Response({'error': 'Person not found'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        admin_user_id = request.data.get('admin_user_id')
        if admin_user_id is None:
            return Response({'message': 'Missing Admin User ID in request data'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            admin_person = Person.objects.get(pk=admin_user_id)
        except Person.DoesNotExist:
            # logger.error(f'Person with ID {admin_user_id} not found')
            return Response({'message': 'Admin Person with that ID does not exist'}, status=status.HTTP_404_NOT_FOUND)
        if not admin_person.is_admin:
            return Response({'message': 'User does not have admin access'}, status=status.HTTP_200_OK)
        surname = request.data.get('surname', 0)
        persons_surname_wise = Surname.objects.filter(Q(id=int(surname))).first()
        father = request.data.get('father', 0)        
        top_member = 0
        if persons_surname_wise: 
            top_member = int(GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0))
            if father == 0 :
                father = top_member
        children = request.data.get('child', [])
        if len(children) > 0 :
            children_exist = ParentChildRelation.objects.filter(child__in=children)
            if children_exist.exclude(parent=top_member).exists():
                return JsonResponse({'message': 'Children already exist'}, status=400)
            children_exist.filter(parent=top_member).delete()
        first_name = request.data.get('first_name')
        middle_name = request.data.get('middle_name')
        address = request.data.get('address')
        out_of_country = request.data.get('out_of_country', 1)
        if (int(out_of_country) == 0) :
            out_of_country = 1
        out_of_address = request.data.get('out_of_address')
        guj_first_name = request.data.get('guj_first_name')
        guj_middle_name = request.data.get('guj_middle_name')
        guj_address = request.data.get('guj_address')
        guj_out_of_address = request.data.get('guj_out_of_address')
        lang = request.data.get('lang')
        if lang is not None and lang != 'en' :
            if guj_first_name is None or guj_first_name  == "":
                return JsonResponse({'message': 'First Name is required'}, status=400)
            # if guj_middle_name is None or guj_middle_name  == "" :
            #     return JsonResponse({'message': 'Middle Name is required'}, status=400)
            # if guj_address is None or guj_address  == "" :
            #     return JsonResponse({'message': 'Address is required'}, status=400)
            if first_name is None or first_name  == "" and guj_first_name is not None and guj_first_name != "":
                first_name = guj_first_name
            if (middle_name is None or middle_name == "") and guj_middle_name is not None and guj_middle_name != "":
                middle_name = guj_middle_name
            if (address is None or address == "") and guj_address is not None and guj_address != "":
                address = guj_address
            if (out_of_address is None or out_of_address == "") and guj_out_of_address is not None and guj_out_of_address != "":
                out_of_address = guj_out_of_address
        date_of_birth = request.data.get('date_of_birth')
        blood_group = request.data.get('blood_group')
        city = request.data.get('city')
        state = request.data.get('state')
        mobile_number1 = request.data.get('mobile_number1')
        mobile_number2 = request.data.get('mobile_number2')
        status_name = request.data.get('status')
        is_admin = request.data.get('is_admin')
        is_registered_directly = request.data.get('is_registered_directly')
        person_data = {
            'first_name': first_name,
            'middle_name': middle_name,
            'address': address,
            'out_of_address': out_of_address,
            'date_of_birth': date_of_birth,
            'blood_group': blood_group,
            'out_of_country' : out_of_country,
            'city': city,
            'state': state,
            'flag_show': True,
            'mobile_number1': mobile_number1,
            'mobile_number2': mobile_number2,
            'status': status_name,
            'surname': surname,
            'is_admin': is_admin,
            'is_registered_directly': is_registered_directly
        }
        serializer = PersonV4Serializer(data=person_data)
        if serializer.is_valid():
            persons = serializer.save()
            parent_serializer = ParentChildRelationSerializer(data={
                                'parent': father, 
                                'child': persons.id,
                                'created_user': persons.id
                            })
            if parent_serializer.is_valid():
                parent_serializer.save()

            for child in children :
                child_serializer = ParentChildRelationSerializer(data={
                                'child': child, 
                                'parent': persons.id,
                                'created_user': persons.id
                            })

                if child_serializer.is_valid():
                    child_serializer.save()
            person_translate_data = {
                'first_name': guj_first_name, 
                'person_id': persons.id,
                'middle_name': guj_middle_name,
                'out_of_address': guj_out_of_address,
                'middle_name': guj_middle_name,
                'address': guj_address,
                'language': lang
            }
            person_translate_serializer = TranslatePersonSerializer(data=person_translate_data)
            if person_translate_serializer.is_valid():
                person_translate_serializer.save()
            return Response({"person": AdminPersonGetSerializer(persons).data}, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    def put(self, request):
        admin_user_id = request.data.get('admin_user_id')
        if not admin_user_id:
            return Response({'message': 'Missing Admin User in request data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        try:
            admin_person = Person.objects.get(pk=admin_user_id)
        except Person.DoesNotExist:
            # logger.error(f'Person with ID {admin_user_id} not found')
            return Response({'message': f'Admin Person not found'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if not admin_person.is_admin and not admin_person.is_super_admin:
            return Response({'message': 'User does not have admin access'}, status=status.HTTP_200_OK)
        
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'message': 'Missing User in request data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        print(request.data)
        person = get_object_or_404(Person, pk=user_id)
        if not person:
            return JsonResponse({'message': 'Person not found'}, status=status.HTTP_400_BAD_REQUEST)
        surname = request.data.get('surname', 0)
        persons_surname_wise = Surname.objects.filter(Q(id=int(surname))).first()
        father = request.data.get('father', 0) 
        top_member = 0
        if persons_surname_wise: 
            top_member = int(GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0))
            if father == 0:
                father = top_member
        children = request.data.get('child', [])
        first_name = request.data.get('first_name')
        middle_name = request.data.get('middle_name')
        address = request.data.get('address')
        out_of_address = request.data.get('out_of_address')
        lang = request.data.get('lang', 'en')
        date_of_birth = request.data.get('date_of_birth')
        blood_group = request.data.get('blood_group', 1)
        # city = request.data.get('city')
        # state = request.data.get('state')
        out_of_country = request.data.get('out_of_country', 1)
        if (int(out_of_country) == 0) :
            out_of_country = 1
        guj_first_name = request.data.get('guj_first_name')
        guj_middle_name = request.data.get('guj_middle_name')
        guj_address = request.data.get('guj_address')
        guj_out_of_address = request.data.get('guj_out_of_address')
        flag_show = request.data.get('flag_show')
        if flag_show is None:
            flag_show = True
        mobile_number1 = request.data.get('mobile_number1')
        mobile_number2 = request.data.get('mobile_number2')

        status_name = request.data.get('status')
        is_admin = request.data.get('is_admin')
        is_registered_directly = request.data.get('is_registered_directly')
        person_data = {
            'first_name' : first_name,
            'middle_name' : middle_name,
            'address' : address,
            'out_of_address': out_of_address,
            'date_of_birth': date_of_birth,
            'blood_group': blood_group,
            # 'city': city,
            # 'state': state,
            'out_of_country': out_of_country,
            'flag_show': flag_show,
            'mobile_number1': mobile_number1,
            'mobile_number2': mobile_number2,
            'status': status_name,
            'surname': surname,
            # 'is_admin': is_admin,
            # 'is_registered_directly': is_registered_directly
        }
        print("Person", person_data)
        
        serializer = PersonV4Serializer(person, data=person_data, context={'person_id': person.id})
        if serializer.is_valid():
            if len(children) > 0:
                children_exist = ParentChildRelation.objects.filter(child__in=children)
                if children_exist.exclude(parent=top_member).exclude(parent=person.id).exists():
                    return JsonResponse({'message': 'Children already exist'}, status=status.HTTP_400_BAD_REQUEST)
            
            persons = serializer.save()

            father_data = ParentChildRelation.objects.filter(child=persons.id)
            if father_data.exists():
                father_data.update(child=persons.id, parent=father)
            else :
                ParentChildRelation.objects.create(child=persons.id, parent=father, created_user=admin_user_id)

            for child in children:
                child_data = ParentChildRelation.objects.filter(child=child)
                if child_data.exists() :
                    child_data.update(parent=persons.id, child=child)
                else :
                    ParentChildRelation.objects.create(child=child, parent=persons.id, created_user=admin_user_id)

            if len(children) > 0:       
                remove_child_person = ParentChildRelation.objects.filter(parent=persons.id).exclude(child__in=children)
                if remove_child_person.exists():
                    for child in remove_child_person:
                        child.update(parent_id= int(top_member))
                            
            lang_data = TranslatePerson.objects.filter(person_id=persons.id).filter(language='guj')
            if lang_data.exists() :
                lang_data = lang_data.update(first_name=guj_first_name, middle_name=guj_middle_name, address=guj_address, out_of_address=guj_out_of_address)
            else:
                lang_data = TranslatePerson.objects.create(person_id=persons.id, first_name=guj_first_name, middle_name=guj_middle_name, address=guj_address,out_of_address=guj_out_of_address, language=lang)
               
            return Response({"person": AdminPersonGetSerializer(persons, context={'lang': lang}).data}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
class V4SearchbyPerson(APIView):
    def post(self, request):
        lang = request.data.get("lang", "en")
        search = request.data.get("search", "")
        person_id = request.data.get("person_id")

        if search == "":
            return JsonResponse({"data": []}, status=200)

        # Get logged in person
        try:
            login_person = Person.objects.select_related(
                "samaj__village"
            ).get(id=person_id, is_deleted=False)
        except Person.DoesNotExist:
            return JsonResponse({"message": "Person not found"}, status=404)

        # Build search query
        search_keywords = search.split(" ")
        search_q = Q()
        for keyword in search_keywords:
            search_q &= (
                Q(first_name__icontains=keyword)
                | Q(date_of_birth__icontains=keyword)
                | Q(mobile_number1__icontains=keyword)
                | Q(mobile_number2__icontains=keyword)
                | Q(surname__name__icontains=keyword)
                | Q(surname__guj_name__icontains=keyword)
                | Q(translateperson__first_name__icontains=keyword)
            )

        # Samaj + Village restriction
        base_filter = Q(
            samaj_id=login_person.samaj_id,
            samaj__village_id=login_person.samaj.village_id,
            flag_show=True,
            is_deleted=False,
        )

        persons = (
            Person.objects.filter(search_q & base_filter)
            .exclude(
                id__in=Surname.objects.annotate(
                    top_member_as_int=Cast("top_member", IntegerField())
                ).values_list("top_member_as_int", flat=True)
            )
            .select_related("surname", "samaj__village")
            .distinct()
            .order_by(
                "first_name",
                "translateperson__first_name",
                "middle_name",
                "translateperson__middle_name",
                "surname__name",
            )
        )

        data = PersonGetDataSortSerializer(
            persons, many=True, context={"lang": lang}
        )

        return JsonResponse({"data": data.data}, status=200)

class V4PendingApproveDetailView(APIView):
    authentication_classes = []
    def post(self, request, format=None):
        lang = request.data.get('lang', 'en')
        try:
            user_id = request.data.get('admin_user_id')
            if not user_id:
                return Response({'message': 'Missing Admin User in request data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            try:
                person = Person.objects.get(pk=user_id)
            except Person.DoesNotExist:
                logger.error(f'Person with ID {user_id} not found')
                return Response({'message': 'User not found'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            if not person.is_admin and not person.is_super_admin:
                return Response({'message': 'User does not have admin access'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            top_member_ids = Surname.objects.exclude(top_member=None).exclude(top_member='').values_list('top_member', flat=True)
            top_member_ids = [int(id) for id in top_member_ids]
            pending_users = Person.objects.filter(flag_show=False).exclude(pk__in=top_member_ids)
            surname = (
                person.surname
            )
            if person.is_admin:
                pending_users = Person.objects.filter(
                        flag_show=False, surname=surname, is_deleted=False
                    ).exclude(id=surname.top_member)
            else:
                pending_users = Person.objects.filter(
                    flag_show=False, is_deleted=False
                ).exclude(id=surname.top_member)

            if not pending_users.exists():
                logger.info('No users with flag_show=False and excluding top_members found')
                return Response({'message': 'No users with pending confirmation'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            serializer = PersonGetSerializer2(pending_users, many=True, context={'lang': lang})
            return Response({'data' : serializer.data}, status=status.HTTP_200_OK)
        except ValueError:
            return Response({'message': 'Invalid top_member ID found in Surname table'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f'An unexpected error occurred: {str(e)}')
            return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def put(self, request, format=None):
        try:
            admin_user_id = request.data.get('admin_user_id')
            if not admin_user_id:
                return Response({'message': 'Missing Admin User in request data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            try:
                admin_person = Person.objects.get(pk=admin_user_id)
            except Person.DoesNotExist:
                logger.error(f'Person with ID {admin_user_id} not found')
                return Response({'message': f'Admin Person not found'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            if not admin_person.is_admin:
                return Response({'message': 'User does not have admin access'}, status=status.HTTP_200_OK)
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({'message': 'Missing User in request data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            try:
                person = Person.objects.get(pk=user_id)
            except Person.DoesNotExist:
                logger.error(f'Person with ID {user_id} not found')
                return Response({'message': f'Person not found'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            if person.flag_show:
                return Response({'message': 'User Already Approved'}, status=status.HTTP_202_ACCEPTED)
            flag_show = request.data.get('flag_show', person.flag_show)
            person.flag_show = flag_show
            person.save()
            serializer = PersonGetSerializer(person)
            return Response({'data': serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f'An unexpected error occurred: {str(e)}')
            return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def delete(self, request):
        try:
            admin_user_id = request.data.get('admin_user_id')
            if not admin_user_id:
                return Response({'message': 'Missing Admin User in request data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            try:
                admin_person = Person.objects.get(pk=admin_user_id)
            except Person.DoesNotExist:
                logger.error(f'Person with ID {admin_user_id} not found')
                return Response({'message': f'Admin Person not found'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            if not admin_person.is_admin:
                return Response({'message': 'User does not have admin access'}, status=status.HTTP_200_OK)
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({'message': 'Missing User in request data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            try:
                person = Person.objects.get(pk=user_id)
            except Person.DoesNotExist:
                logger.error(f'Person with ID {user_id} not found')
                return Response({'message': f'Person not found'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            try:
                translate_person = TranslatePerson.objects.get(person_id=user_id)
                translate_person.delete()
            except TranslatePerson.DoesNotExist:
                logger.error(f'TranslatePerson with ID {user_id} not found')
                pass
            try:
                top_member_ids = Surname.objects.filter(name=person.surname).values_list('top_member', flat=True)
                top_member_ids = [int(id) for id in top_member_ids]
                if len(top_member_ids) > 0:
                    children = ParentChildRelation.objects.filter(parent_id=user_id)
                    for child in children:
                        child.parent_id = top_member_ids[0]
                        child.save()
            except Surname.DoesNotExist:
                print(f'TranslatePerson with ID {user_id} not found')
                return Response({"message": f"Surname not exist"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            except Exception as exp:
                print(f'TranslatePerson with ID {user_id} not found')
                return Response({"message": f"${exp}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            person.delete()
            return Response({"message": f"Person deleted successfully."}, status=status.HTTP_200_OK)
        except Http404:
            return Response({"message": f"Person not found."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({"message": f"Failed to delete the for this record"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)