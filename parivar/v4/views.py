from io import BytesIO
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Prefetch, F, Q, Count, OuterRef, Subquery, Value, CharField, When, Case, IntegerField
from django.db import transaction, IntegrityError
from django.db.models.functions import Cast, Coalesce
from django.core import signing
from django.urls import reverse
from PIL import Image, ImageFile
from django.core.files import File
from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.db.models.functions import Concat
from django.db import transaction, IntegrityError
from datetime import datetime, timedelta
import numpy as np
import cv2
import string
import random

from parivar.services import CSVImportService
from ..models import (
    Person, District, Taluka, User, Village, Samaj, State, City,
    TranslatePerson, Surname, ParentChildRelation, Country,
    BloodGroup, Banner, AdsSetting, PersonUpdateLog, RandomBanner,
    # DemoPerson, DemoParentChildRelation, DemoSurname
)
# from ..services import LocationResolverService, CSVImportService
from django.conf import settings
from notifications.models import PersonPlayerId
from ..utils import get_person_queryset, get_relation_queryset
from ..serializers import (
    CountryWiseMemberSerializer,
    DistrictSerializer,
    PersonGetSerializer,
    PersonGetSerializer4,
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
    PersonGetV4Serializer,
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
# from ..views import compress_image, getadmincontact
import logging
import os
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from random import choices
import logging

logger = logging.getLogger(__name__)

ImageFile.LOAD_TRUNCATED_IMAGES = True


prototxt_path = os.getenv("PROTO_TXT_PATH")
model_path = os.getenv("MODEL_PATH")
net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)


def find_faces_and_crop(image, aspect_ratio=(1, 1), padding_ratio=50):
    # Convert PIL Image to an OpenCV Image
    cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    # Get the image dimensions
    (h, w) = cv_image.shape[:2]

    # Preprocess the image: mean subtraction, scaling, and swapping Red and Blue channels
    blob = cv2.dnn.blobFromImage(cv_image, 1.0, (300, 300), (104.0, 177.0, 123.0))

    # Pass the blob through the network to detect faces
    net.setInput(blob)
    detections = net.forward()

    cropped_images = []

    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > 0.5:
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (startX, startY, endX, endY) = box.astype("int")

            # Calculate the center of the face
            centerX, centerY = (startX + endX) // 2, (startY + endY) // 2

            # Calculate the width and height based on the desired aspect ratio
            face_width = endX - startX
            face_height = face_width * aspect_ratio[1] // aspect_ratio[0]

            # Add padding to include neck and hair
            padding = int(padding_ratio)
            crop_top = max(centerY - face_height - padding // 2, 0)
            crop_bottom = min(centerY + face_height + padding // 2, h)

            # Ensure the dimensions do not exceed the image boundaries
            crop_left = max(centerX - face_width - padding // 2, 0)
            crop_right = min(centerX + face_width + padding // 2, w)

            # Crop the image to the calculated dimensions
            img_cropped = image.crop((crop_left, crop_top, crop_right, crop_bottom))
            cropped_images.append(img_cropped)

    return cropped_images


def get_dominant_color(image, num_colors=1):
    """Returns the dominant color(s) in the image."""
    image = image.convert("RGB")
    pixels = np.array(image).reshape(-1, 3)
    colors, count = np.unique(pixels, axis=0, return_counts=True)
    sorted_indices = np.argsort(count)[::-1]
    dominant_colors = colors[sorted_indices][:num_colors]
    return tuple(dominant_colors[0])


def compress_image(input_path, output_folder, size=(300, 300), quality=40):
    img = Image.open(input_path)
    cropped_images = find_faces_and_crop(img)  # Crop image to center each face if found
    for idx, img_cropped in enumerate(cropped_images):
        img_cropped.thumbnail(size, Image.Resampling.LANCZOS)

        dominant_color = get_dominant_color(img_cropped)

        new_img = Image.new("RGB", size, dominant_color)

        paste_x = (size[0] - img_cropped.width) // 2
        paste_y = (size[1] - img_cropped.height) // 2

        new_img.paste(img_cropped, (paste_x, paste_y))
        fileName = f"{os.path.splitext(os.path.basename(input_path.path))[0]}.jpg"
        try:
            output_path = os.path.join(output_folder.path, fileName)
        except Exception as e:
            output_path = os.path.join("compress_img", fileName)
            pass
        # new_img.save(output_path, optimize=True, quality=quality)  # Save with compression
        buffer = BytesIO()
        new_img.save(buffer, format="JPEG")
        django_file = File(buffer, name=fileName)
        output_folder.save(fileName, django_file, save=True)
        return output_path

def getadmincontact(flag_show=False, lang="en", surname=None):
    if flag_show == False:
        admin = None
        if surname is not None:
            if lang == "guj":
                admin = Person.objects.filter(
                    surname__guj_name=surname,
                    flag_show=True,
                    is_admin=True,
                    is_deleted=False,
                )
            else:
                admin = Person.objects.filter(
                    surname__name=surname,
                    flag_show=True,
                    is_admin=True,
                    is_deleted=False,
                )
        if admin.exists():
            admin_serializer = PersonGetSerializer(
                admin, context={"lang": lang}, many=True
            )
            admin_data = admin_serializer.data
        else:
            admin_data = []

        super_admin = Person.objects.filter(
            flag_show=True, is_admin=True, is_deleted=False
        )
        admin_serializer1 = PersonGetSerializer(
            super_admin, context={"lang": lang}, many=True
        )
        super_admin_data = admin_serializer1.data
        combined_data = sorted(
            super_admin_data,
            key=lambda x: (
                x["surname"],  # Primary sorting by surname
                x["first_name"],  # Secondary sorting by first name
            ),
        )
        combined_data = sorted(
            combined_data,
            key=lambda x: (x["surname"] != surname, x["surname"], x["first_name"]),
        )

        if lang == "guj":
            error_message = (
                "તમારી નવા સભ્ય માં નોંધણી થઈ ગઈ છે. હવે તમે કૃપા કરી ને કાર્યકર્તાને સંપર્ક કરો."
            )
        else:
            error_message = "You are successfully registered as one of our members. Now you can contact your admin."

        return {
            "message": error_message,
            "admin_data": admin_data + combined_data,
        }

    return {"message": "", "admin_data": []}

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
        login_person = get_person_queryset(request).filter(
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

        # Filter surnames linked to login user's specific samaj
        surnames = Surname.objects.filter(samaj_id=login_person.samaj_id).order_by("name")
        serializer = SurnameSerializer(surnames, many=True, context={"lang": lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

class GetSurnameBySamajView(APIView):
    """Returns all surnames for a specific samaj."""
    @swagger_auto_schema(
        operation_description="Get surnames for a specific samaj",
        manual_parameters=[
            openapi.Parameter('samaj_id', openapi.IN_QUERY, description="Samaj ID", type=openapi.TYPE_INTEGER, required=True),
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING),
        ],
        responses={200: openapi.Response(description="Surnames list", schema=SurnameSerializer(many=True)), 400: "Samaj ID is required"}
    )
    def get(self, request):
        samaj_id = request.GET.get("samaj_id")
        if not samaj_id:
            return Response({"error": "Samaj ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        lang = request.GET.get("lang", "en")

        surnames = Surname.objects.filter(samaj_id=samaj_id).order_by('name')
        serializer = SurnameSerializer(surnames, many=True, context={"lang": lang})

        # Annotate total person count per surname
        from django.db.models import Count, Q as DQ
        surname_counts = {
            item["surname_id"]: item["total"]
            for item in get_person_queryset(request).filter(
                surname__samaj_id=samaj_id,
                is_deleted=False,
                flag_show=True,
            ).values("surname_id").annotate(total=Count("id"))
        }

        data = serializer.data
        for item in data:
            item["total_count"] = str(surname_counts.get(item["id"], 0))

        return Response(data, status=status.HTTP_200_OK)

    
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
            person = get_person_queryset(request).get(
                Q(mobile_number1=mobile_number) | Q(mobile_number2=mobile_number)
            )
        except Person.DoesNotExist:
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

        admin_list = {}
        admin_list["person"] = serializer.data

        login_surname = person.surname
        login_samaj   = person.samaj
        login_village = person.samaj.village if person.samaj else None

        # STEP 1 — SAME SURNAME + SAME SAMAJ ADMINS
        # (Since Surname is now localized to Samaj, filtering by both is redundant but safe)
        admin_queryset = get_person_queryset(request).filter(
            surname=login_surname,
            samaj=login_samaj,
            is_admin=True,
            flag_show=True
        ).exclude(id=person.id)


        # STEP 2 — IF NO ADMIN → VILLAGE SUPER ADMIN
        if admin_queryset.exists():

            final_admin_queryset = admin_queryset

        else:
            final_admin_queryset = get_person_queryset(request).filter(
                samaj__village=login_village,
                is_admin=True,
                flag_show=True
            ).exclude(id=person.id)

        # FINAL RESPONSE
        admin_list["admin_data"] = PersonGetV4Serializer(
            final_admin_queryset,
            many=True,
            context={"lang": lang}
        ).data
       
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
                person_obj = get_person_queryset(request).get(pk=admin_user_id)
                print("Person object for pending data count:", type(person_obj))
                if person_obj.is_admin:
                    if person_obj.is_admin:
                        pending_users = get_person_queryset(request).filter(
                            flag_show=False
                        )
                        print("Pending users for super admin:", pending_users)
                    else:
                        pending_users = get_person_queryset(request).filter(
                            flag_show=False, 
                            samaj=person_obj.samaj,
                            surname=person_obj.surname
                        ).exclude(id=person_obj.surname.top_member if person_obj.surname else None)
                    pendingdata_count = pending_users.count()
                    print("Pending data count:", pendingdata_count)
                else:
                    pendingdata_count = 0
            except Person.DoesNotExist:
                pendingdata_count = 0
            
            response_data = {"pending-data": pendingdata_count}
            response_data.update(admin_list)
            return Response(response_data, status=status.HTTP_200_OK)
            
        return Response(admin_list, status=status.HTTP_200_OK)


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
        lang = request.GET.get("lang", "en")
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
        lang = request.GET.get("lang", "en")
        try:
            taluka = Taluka.objects.select_related('district').get(pk=taluka_id)
            if not taluka.is_active or not taluka.district.is_active:
                return Response({"message": "Location deactivated. Please contact admin."}, status=status.HTTP_403_FORBIDDEN)
            serializer = DistrictSerializer(taluka.district, context={'lang': request.GET.get("lang", "en")})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Taluka.DoesNotExist:
            return Response({"error": "Taluka not found"}, status=status.HTTP_404_NOT_FOUND)
        

class  V4RelationtreeAPIView(APIView):

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
           login_person = get_person_queryset(request).filter(
               Q(mobile_number1=mobile_number) |
               Q(mobile_number2=mobile_number),
           ).select_related("samaj__village").first()

           if login_person and login_person.samaj and login_person.samaj.village_id:
               login_village_id = login_person.samaj.village_id

           if not login_village_id:
               return Response(
                   {"error": "Login person's village information is required"},
                   status=status.HTTP_400_BAD_REQUEST
               )
       try:
           person = get_person_queryset(request).get(id=person_id)
           surname = person.surname.id
           surname_topmember = Surname.objects.get(id=surname)
           topmember = surname_topmember.top_member
           # Walk ancestor chain: batch lookups using child_id__in to reduce queries
           relation_qs = get_relation_queryset(request)
           parent_data_id = set([person_id])
           to_process = [person_id]

           while to_process:
               # fetch parent ids for current batch (no unnecessary joins)
               parent_ids = list(
                   relation_qs.filter(child_id__in=to_process).values_list("parent_id", flat=True)
               )
               to_process = []
               for parent_id in parent_ids:
                   if parent_id == topmember:
                       continue
                   if parent_id not in parent_data_id:
                       parent_data_id.add(parent_id)
                       to_process.append(parent_id)
           person_data_queryset = (
               get_person_queryset(request).filter(
                   surname__id=surname, flag_show=True
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

               .select_related("samaj__village", "out_of_country")

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
                existing_relation = get_relation_queryset(request).get(
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
                login_person = get_person_queryset(request).filter(
                    Q(mobile_number1=mobile_number) |
                    Q(mobile_number2=mobile_number),
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
                get_person_queryset(request).filter(surname__id=surnameid)
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
                get_relation_queryset(request).filter(
                    Q(parent__surname__id=surnameid)
                    & Q(child__surname__id=surnameid),
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
                            GetSurnameSerializer(surname_data).data.get("top_member", 0) or 0
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
            created_user = get_person_queryset(request).get(id=created_user_id, is_deleted=False)
        except Person.DoesNotExist:
            return Response(
                {"error": "Admin memeber not found."}, status=status.HTTP_404_NOT_FOUND
            )
        if not created_user.is_admin:
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
            parent = get_person_queryset(request).get(id=parent_id, is_deleted=False)
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
            child = get_person_queryset(request).get(id=child_id, is_deleted=False)
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
            relation = get_relation_queryset(request).get(child=child, is_deleted=False)
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
            person = Person.objects.filter(is_deleted=False).get(id=pk)
            if person:
                lang = request.GET.get('lang', 'en')
                person = PersonGetV4Serializer(person, context={'lang': lang}).data
                person['is_admin'] = person.get('is_admin', False) or person.get('is_super_admin', False) or person.get('is_super_uper', False)
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
            top_member = int(GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0) or 0)
            if father == 0 :
                father = top_member
        children = request.data.get('child', [])
        first_name = request.data.get('first_name')
        middle_name = request.data.get('middle_name')
        address = request.data.get('address')
        out_of_address = request.data.get('out_of_address')
        guj_first_name = request.data.get('guj_first_name') or request.data.get('trans_first_name')
        guj_middle_name = request.data.get('guj_middle_name') or request.data.get('trans_middle_name')
        guj_address = request.data.get('guj_address')
        guj_out_of_address = request.data.get('guj_out_of_address')
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
            'samaj': samaj_id,
            'is_admin': is_admin,
            'is_registered_directly': is_registered_directly
        }
        serializer = PersonV4Serializer(data=person_data)
        if serializer.is_valid():
            if len(children) > 0 :
                children_exist = get_relation_queryset(request).filter(child__in=children)
                if children_exist.exclude(parent=top_member).exists():
                    return JsonResponse({'message': 'Children already exist'}, status=400)
                children_exist.filter(parent=top_member).delete()
            persons = serializer.save()
            if surname:
                persons.surname_id = surname
            if samaj_id:
                persons.samaj_id = samaj_id
            persons.save()
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
            if guj_first_name or guj_middle_name:
                person_translate_data = {
                    'first_name': guj_first_name,
                    'person_id': persons.id,
                    'middle_name': guj_middle_name,
                    'address': guj_address,
                    'out_of_address': guj_out_of_address,
                    'language': 'guj'
                }
                person_translate_serializer = TranslatePersonSerializer(data=person_translate_data)
                if person_translate_serializer.is_valid():
                    person_translate_serializer.save()
            elif (lang != "en"):   
                person_translate_data = {
                    'first_name': first_name,
                    'person_id': persons.id,
                    'middle_name': middle_name,
                    'address': address,
                    'out_of_address': out_of_address,
                    'language': lang
                }
                person_translate_serializer = TranslatePersonSerializer(data=person_translate_data)
                if person_translate_serializer.is_valid():
                    person_translate_serializer.save()
            return Response(PersonGetV4Serializer(persons, context={'lang': lang}).data, status=status.HTTP_201_CREATED)
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
            top_member = int(GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0) or 0)
            if father == 0:
                father = top_member
        children = request.data.get('child', [])
        first_name = request.data.get('first_name')
        middle_name = request.data.get('middle_name')
        address = request.data.get('address')
        out_of_address = request.data.get('out_of_address')
        guj_first_name = request.data.get('guj_first_name') or request.data.get('trans_first_name')
        guj_middle_name = request.data.get('guj_middle_name') or request.data.get('trans_middle_name')
        guj_address = request.data.get('guj_address')
        guj_out_of_address = request.data.get('guj_out_of_address')
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
        samaj_id = request.data.get('samaj', person.samaj_id)
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
            'samaj': samaj_id,
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
                children_exist = get_relation_queryset(request).filter(child__in=children)
                if children_exist.exclude(parent=top_member).exclude(parent=person.id).exists():
                    return JsonResponse({'message': 'Children already exist'}, status=400)
            persons = serializer.save()
            if surname:
                persons.surname_id = surname
            if samaj_id:
                persons.samaj_id = samaj_id
            persons.save()
 
            father_data = get_relation_queryset(request).filter(child=persons.id)
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
                child_data = get_relation_queryset(request).filter(child=child)
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
                remove_child_person = get_relation_queryset(request).filter(parent=persons.id).exclude(child__in=children)
                if remove_child_person.exists():
                    for child in remove_child_person:
                        child.parent_id = int(top_member)
                        child.save()
            if guj_first_name or guj_middle_name:
                lang_data = TranslatePerson.objects.filter(person_id=persons.id, language='guj')
                if lang_data.exists():
                    lang_data.update(first_name=guj_first_name, middle_name=guj_middle_name, address=guj_address, out_of_address=guj_out_of_address)
                else:
                    TranslatePerson.objects.create(person_id=persons, first_name=guj_first_name, middle_name=guj_middle_name, address=guj_address, out_of_address=guj_out_of_address, language='guj')
            elif (lang != "en"):
                lang_data = TranslatePerson.objects.filter(person_id=persons.id, language=lang)
                if lang_data.exists() :
                    lang_data = lang_data.first()
                    person_translate_data = {
                        'first_name': first_name,
                        'middle_name': middle_name,
                        'address': address,
                        'out_of_address': out_of_address,
                        'language': lang
                    }
                    person_translate_serializer = TranslatePersonSerializer(lang_data, data=person_translate_data)
                    if person_translate_serializer.is_valid():
                        person_translate_serializer.save()
            return Response({
                "person": PersonGetV4Serializer(persons, context={'lang': lang}).data
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
            admin_person = get_person_queryset(request).get(pk=admin_user_id, is_deleted=False)
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
        if not admin_person.is_admin:
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
        admin_data = get_person_queryset(request).filter(
            Q(is_admin=True)
        )
        serializer = PersonGetV4Serializer(admin_data, context={"lang": lang}, many=True)
        return Response({"admin-data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        lang = request.data.get("lang", "en")
        mobile = request.data.get("mobile")
        admin_user_id = request.data.get("admin_user_id")
        if not mobile:
            return Response(
                {"message": "Mobile number list is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if isinstance(mobile, str):
            mobile = [mobile]
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
            admin_person = get_person_queryset(request).get(pk=admin_user_id)
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
        if not admin_person.is_admin:
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
        admin_access = get_person_queryset(request).filter(
            Q(mobile_number1__in=mobile) | Q(mobile_number2__in=mobile),
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
            admin_person = get_person_queryset(request).get(pk=admin_user_id)
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
        if not admin_person.is_admin:
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
        admin_access = get_person_queryset(request).filter(
            Q(mobile_number1__in=mobile) | Q(mobile_number2__in=mobile),
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
            person = get_person_queryset(request).get(id=person_id)
        except Person.DoesNotExist:
            return Response(
                {"message": "Person Not Found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Cross-validate X-Mobile-Number header
        mobile_header = request.headers.get("X-Mobile-Number")
        if mobile_header:
            if (
                person.mobile_number1 != mobile_header
                and person.mobile_number2 != mobile_header
            ):
                return Response(
                    {"message": "Unauthorized: Mobile number does not match person"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        lang = request.GET.get("lang", "en")
        # ===== Permission Based Admin List =====

        if person.is_admin:
            # All admins get full list
            admin_persons = get_person_queryset(request).filter(
                Q(is_admin=True),
            )

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

        # Cross-validate X-Mobile-Number header — must belong to same samaj as surname's top member
        mobile_header = request.headers.get("X-Mobile-Number")
        if mobile_header:
            try:
                requester = get_person_queryset(request).filter(
                    Q(mobile_number1=mobile_header) | Q(mobile_number2=mobile_header),
                    is_deleted=False
                ).select_related("samaj").first()

                top_member_id = Surname.objects.filter(id=int(surname)).values_list("top_member", flat=True).first()
                if top_member_id:
                    top_member_person = get_person_queryset(request).filter(id=top_member_id, is_deleted=False).select_related("samaj").first()
                    if (
                        not requester
                        or not top_member_person
                        or requester.samaj_id != top_member_person.samaj_id
                    ):
                        return Response(
                            {"message": "Unauthorized: Mobile number does not belong to the same samaj"},
                            status=status.HTTP_403_FORBIDDEN,
                        )
            except Exception:
                pass

        surname_data = Surname.objects.filter(Q(id=int(surname)))
        if surname_data.exists():
            surname_data = surname_data.first()
            top_member = int(
                GetSurnameSerializer(surname_data).data.get("top_member", 0)
            )
            persons = (
                get_person_queryset(request).filter(
                    Q(surname__id=int(surname)),
                    is_admin=False,
                    flag_show=True,
                    mobile_number1__isnull=False,
                )
                .exclude(id=top_member)
                .exclude(mobile_number1=["", None])
                .order_by("first_name")
            )
            if persons.exists():
                serializer = PersonGetV4Serializer(
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
            person = get_person_queryset(request).get(id=admin_user_id, is_deleted=False)

            # Cross-validate X-Mobile-Number header
            mobile_header = request.headers.get("X-Mobile-Number")
            if mobile_header:
                if (
                    person.mobile_number1 != mobile_header
                    and person.mobile_number2 != mobile_header
                ):
                    return Response(
                        {"message": "Unauthorized: Mobile number does not match admin user"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
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
    def get(self, request, pk, admin_user_id):
        admin_user_id = admin_user_id
        if not admin_user_id:
            return Response({'message': 'Missing Admin User in request data'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            admin_person = get_person_queryset(request).get(pk=admin_user_id)
        except Person.DoesNotExist:
            return Response({'message': 'Admin Person not found'}, status=status.HTTP_404_NOT_FOUND)
        if not admin_person.is_admin:
            return Response({'message': 'User does not have admin access'}, status=status.HTTP_403_FORBIDDEN)

        # Cross-validate X-Mobile-Number header
        mobile_header = request.headers.get("X-Mobile-Number")
        if mobile_header:
            if (
                admin_person.mobile_number1 != mobile_header
                and admin_person.mobile_number2 != mobile_header
            ):
                return Response(
                    {'message': 'Unauthorized: Mobile number does not match admin user'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        try:
            person = get_person_queryset(request).get(id=pk)
            if person:
                lang = request.GET.get('lang', 'en')
                person = AdminPersonGetSerializer(person, context={'lang': lang}).data
                person['is_admin'] = person.get('is_admin', False) or person.get('is_super_admin', False) or person.get('is_super_uper', False)
                person['child'] = []
                person['parent'] = {}
                person['brother'] = []
                child_data = get_relation_queryset(request).filter(parent=int(person["id"]))
                if child_data.exists():
                    child_data = GetParentChildRelationSerializer(child_data, many=True, context={'lang': lang}).data
                    for child in child_data:
                        person['child'].append(child.get("child"))
                parent_data = get_relation_queryset(request).filter(child=int(person["id"])).first()
                if parent_data:
                    parent_data = GetParentChildRelationSerializer(parent_data, context={'lang': lang}).data
                    person['parent'] = parent_data.get("parent")
                    brother_data = get_relation_queryset(request).filter(parent=int(parent_data.get("parent").get("id", 0)))
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
            admin_person = get_person_queryset(request).get(pk=admin_user_id)
        except Person.DoesNotExist:
            return Response({'message': 'Admin Person with that ID does not exist'}, status=status.HTTP_404_NOT_FOUND)
        if not admin_person.is_admin:
            return Response({'message': 'User does not have admin access'}, status=status.HTTP_403_FORBIDDEN)

        # Cross-validate X-Mobile-Number header
        mobile_header = request.headers.get("X-Mobile-Number")
        if mobile_header:
            if (
                admin_person.mobile_number1 != mobile_header
                and admin_person.mobile_number2 != mobile_header
            ):
                return Response(
                    {'message': 'Unauthorized: Mobile number does not match admin user'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        surname = request.data.get('surname', 0)
        persons_surname_wise = Surname.objects.filter(Q(id=int(surname))).first()
        father = request.data.get('father', 0)        
        top_member = 0
        if persons_surname_wise:
            top_member = int(GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0) or 0)
            if father == 0 :
                father = top_member
        children = request.data.get('child', [])
        if len(children) > 0 :
            children_exist = get_relation_queryset(request).filter(child__in=children)
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
        guj_first_name = request.data.get('guj_first_name') or request.data.get('trans_first_name')
        guj_middle_name = request.data.get('guj_middle_name') or request.data.get('trans_middle_name')
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
        samaj_id = request.data.get('samaj')
        # Auto-resolve samaj if not explicitly provided:
        # 1. Prefer the samaj linked to the selected surname (Surname.samaj FK)
        # 2. Fall back to looking up by village ID sent in request
        if not samaj_id and persons_surname_wise and persons_surname_wise.samaj_id:
            samaj_id = persons_surname_wise.samaj_id
        if not samaj_id:
            village_id = request.data.get('village')
            if village_id:
                samaj_from_village = Samaj.objects.filter(village_id=int(village_id)).first()
                if samaj_from_village:
                    samaj_id = samaj_from_village.id
                    
        is_demo_user = admin_person.is_demo if admin_person else False

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
            'samaj': samaj_id,
            'is_admin': is_admin,
            'is_demo': is_demo_user,
            'is_registered_directly': is_registered_directly
        }
        serializer = PersonV4Serializer(data=person_data)
        if serializer.is_valid():
            persons = serializer.save()

            # surname, city, state, samaj, out_of_country are SerializerMethodField
            # (read-only) in PersonV4Serializer, so they are NOT saved by serializer.save().
            # Validate each FK against DB before assigning to avoid IntegrityErrors.
            fk_update_fields = []

            # Surname: use the already-queried object (guaranteed to exist)
            if persons_surname_wise:
                persons.surname_id = persons_surname_wise.id
                fk_update_fields.append('surname')

            # City: look up first to ensure it exists
            if city:
                try:
                    city_obj = City.objects.filter(pk=int(city)).first()
                    if city_obj:
                        persons.city_id = city_obj.id
                        fk_update_fields.append('city')
                except (ValueError, TypeError):
                    pass

            # State: look up first to ensure it exists
            if state:
                try:
                    city_state_obj = State.objects.filter(pk=int(state)).first()
                    if city_state_obj:
                        persons.state_id = city_state_obj.id
                        fk_update_fields.append('state')
                except (ValueError, TypeError):
                    pass

            # Samaj: use resolved samaj_id (from surname or village fallback above)
            if samaj_id:
                try:
                    samaj_obj = Samaj.objects.filter(pk=int(samaj_id)).first()
                    if samaj_obj:
                        persons.samaj_id = samaj_obj.id
                        fk_update_fields.append('samaj')
                except (ValueError, TypeError):
                    pass

            # Country: look up first to ensure it exists
            if out_of_country:
                try:
                    country_obj = Country.objects.filter(pk=int(out_of_country)).first()
                    if country_obj:
                        persons.out_of_country_id = country_obj.id
                        fk_update_fields.append('out_of_country')
                except (ValueError, TypeError):
                    pass

            if fk_update_fields:
                persons.save(update_fields=fk_update_fields)

            # Refresh from DB to clear in-memory FK caches (samaj→village→taluka→district)
            persons.refresh_from_db()

            parent_serializer = ParentChildRelationSerializer(data={
                                'parent': father,
                                'child': persons.id,
                                'created_user': persons.id,
                                'is_demo': is_demo_user
                            })
            if parent_serializer.is_valid():
                parent_serializer.save()
 
            for child in children :
                child_serializer = ParentChildRelationSerializer(data={
                                'child': child,
                                'parent': persons.id,
                                'created_user': persons.id,
                                'is_demo': is_demo_user
                            })
 
                if child_serializer.is_valid():
                    child_serializer.save()
            if guj_first_name or guj_middle_name:
                person_translate_data = {
                    'first_name': guj_first_name,
                    'person_id': persons.id,
                    'out_of_address': guj_out_of_address,
                    'middle_name': guj_middle_name,
                    'address': guj_address,
                    'language': 'guj'
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
            return Response({'message': 'Missing Admin User in request data'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            admin_person = get_person_queryset(request).get(pk=admin_user_id)
        except Person.DoesNotExist:
            return Response({'message': 'Admin Person not found'}, status=status.HTTP_404_NOT_FOUND)
        if not admin_person.is_admin:
            return Response({'message': 'User does not have admin access'}, status=status.HTTP_403_FORBIDDEN)

        # Cross-validate X-Mobile-Number header
        mobile_header = request.headers.get("X-Mobile-Number")
        if mobile_header:
            if (
                admin_person.mobile_number1 != mobile_header
                and admin_person.mobile_number2 != mobile_header
            ):
                return Response(
                    {'message': 'Unauthorized: Mobile number does not match admin user'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        user_id = request.data.get('id')
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
            top_member = int(GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0) or 0)
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
        guj_first_name = request.data.get('guj_first_name') or request.data.get('trans_first_name')
        guj_middle_name = request.data.get('guj_middle_name') or request.data.get('trans_middle_name')
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
        samaj_id = request.data.get('samaj')
        is_demo_user = admin_person.is_demo if admin_person else False

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
            'is_demo': is_demo_user,
            # 'is_admin': is_admin,
            # 'is_registered_directly': is_registered_directly
        }
        print("Person", person_data)
        
        serializer = PersonV4Serializer(person, data=person_data, context={'person_id': person.id})
        if serializer.is_valid():
            if len(children) > 0:
                children_exist = get_relation_queryset(request).filter(child__in=children)
                if children_exist.exclude(parent=top_member).exclude(parent=person.id).exists():
                    return JsonResponse({'message': 'Children already exist'}, status=status.HTTP_400_BAD_REQUEST)
            
            persons = serializer.save()
 
            father_data = get_relation_queryset(request).filter(child=persons.id)
            if father_data.exists():
                father_data.update(child=persons.id, parent_id=father, is_demo=is_demo_user)
            else:
                ParentChildRelation.objects.create(child=persons, parent_id=father, created_user=persons, is_demo=is_demo_user)
 
            for child in children:
                child_data = get_relation_queryset(request).filter(child=child)
                if child_data.exists() :
                    child_data.update(parent=persons.id, child=child, is_demo=is_demo_user)
                else :
                    ParentChildRelation.objects.create(child=child, parent=persons.id, created_user=admin_user_id, is_demo=is_demo_user)
 
            if len(children) > 0:       
                remove_child_person = get_relation_queryset(request).filter(parent=persons.id).exclude(child__in=children)
                if remove_child_person.exists():
                    for child in remove_child_person:
                        child.update(parent_id= int(top_member))
                            
            if guj_first_name or guj_middle_name:
                lang_data = TranslatePerson.objects.filter(person_id=persons.id, language='guj')
                if lang_data.exists():
                    lang_data.update(first_name=guj_first_name, middle_name=guj_middle_name, address=guj_address, out_of_address=guj_out_of_address)
                else:
                    TranslatePerson.objects.create(person_id=persons, first_name=guj_first_name, middle_name=guj_middle_name, address=guj_address, out_of_address=guj_out_of_address, language='guj')

            persons.refresh_from_db()
            return Response({"person": AdminPersonGetSerializer(persons, context={'lang': lang}).data}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
class V4SearchbyPerson(APIView):
    def post(self, request):
        lang = request.data.get("lang", "en")
        search = request.data.get("search", "")
        person_id = request.data.get("person_id")
        
        mobile_header = request.headers.get("X-Mobile-Number")
        if not mobile_header:
            return JsonResponse({"message": "X-Mobile-Number header is required"}, status=400)
 
        if search == "":
            return JsonResponse({"data": []}, status=200)
 
        # Get logged in person
        try:
            login_person = get_person_queryset(request).select_related(
                "samaj__village"
            ).get(id=person_id)
            
            if login_person.mobile_number1 != mobile_header and login_person.mobile_number2 != mobile_header:
                return JsonResponse({"message": "Unauthorized: Mobile number does not match person"}, status=403)
                
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
            get_person_queryset(request).filter(search_q & base_filter)
             .exclude(
                id__in=Surname.objects.exclude(
                    top_member__in=["", None]
                ).annotate(
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
        lang = request.data.get("lang", "en")
        try:
            admin_user_id = request.data.get("admin_user_id")
            if not admin_user_id:
                message = (
                    "એડમીન મળી રહીયો નથી"
                    if lang == "guj"
                    else "Missing Admin User in request data"
                )
                return Response(
                    {"message": message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            try:
                person = get_person_queryset(request).get(pk=admin_user_id, is_deleted=False)
            except Person.DoesNotExist:
                return Response(
                    {"message": "User not found"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            if not person.is_admin:
                return Response(
                    {"message": "User does not have admin access"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Cross-validate X-Mobile-Number header
            mobile_header = request.headers.get("X-Mobile-Number")
            if mobile_header:
                if (
                    person.mobile_number1 != mobile_header
                    and person.mobile_number2 != mobile_header
                ):
                    return Response(
                        {"message": "Unauthorized: Mobile number does not match admin user"},
                        status=status.HTTP_403_FORBIDDEN,
                    )

            # Get surname based on admin user (assuming relationship exists)
            surname = (
                person.surname
            )  # Modify this line based on your model relationships

            # Filter users by surname instead of top_member
            if person.is_admin == True:
                pending_users = get_person_queryset(request).filter(
                    flag_show=False
                ).exclude(id=surname.top_member)
                if not pending_users.exists():
                    return Response(
                        {
                            "message": "No users with pending confirmation for this surname"
                        },
                        status=status.HTTP_200_OK,
                    )
                child_users = pending_users.filter(child_flag=True).order_by(
                    "first_name"
                )
                other_users = pending_users.filter(child_flag=False).order_by(
                    "first_name"
                )
                data = {
                    "child": PersonV4Serializer(
                        child_users, many=True, context={"lang": lang}
                    ).data,
                    "others": PersonV4Serializer(
                        other_users, many=True, context={"lang": lang}
                    ).data,
                }
            elif person.is_admin == True:

                pending_users = get_person_queryset(request).filter(
                    flag_show=False, surname=surname
                ).exclude(id=surname.top_member)
                if not pending_users.exists():
                    return Response(
                        {
                            "message": "No users with pending confirmation for this surname"
                        },
                        status=status.HTTP_200_OK,
                    )
                child_users = pending_users.filter(child_flag=True).order_by(
                    "first_name"
                )
                other_users = pending_users.exclude(child_flag=True).order_by(
                    "first_name"
                )

                data = {
                    "child": PersonV4Serializer(
                        child_users, many=True, context={"lang": lang}
                    ).data,
                    "others": PersonV4Serializer(
                        other_users, many=True, context={"lang": lang}
                    ).data,
                }

            return Response(
                {"message": "success", "data": data}, status=status.HTTP_200_OK
            )
        except ValueError:
            return Response(
                {"message": "Invalid data provided"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    def put(self, request, format=None):
        try:
            admin_user_id = request.data.get("admin_user_id")
            if not admin_user_id:
                return Response(
                    {"message": "Missing Admin User in request data"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            try:
                admin_person = get_person_queryset(request).get(pk=admin_user_id)
            except Person.DoesNotExist:
                logger.error(f"Person with ID {admin_user_id} not found")
                return Response(
                    {"message": f"Admin Person not found"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            if not admin_person.is_admin:
                return Response(
                    {"message": "User does not have admin access"},
                    status=status.HTTP_200_OK,
                )

            # Cross-validate X-Mobile-Number header
            mobile_header = request.headers.get("X-Mobile-Number")
            if mobile_header:
                if (
                    admin_person.mobile_number1 != mobile_header
                    and admin_person.mobile_number2 != mobile_header
                ):
                    return Response(
                        {"message": "Unauthorized: Mobile number does not match admin user"},
                        status=status.HTTP_403_FORBIDDEN,
                    )

            # Cross-validate: ensure target user belongs to admin's surname (non-super admin)
            user_id = request.data.get("user_id")
            if not user_id:
                return Response(
                    {"message": "Missing User in request data"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            try:
                person = get_person_queryset(request).get(pk=user_id)
            except Person.DoesNotExist:
                logger.error(f"Person with ID {user_id} not found")
                return Response(
                    {"message": f"Person not found"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            if not admin_person.is_admin and person.surname != admin_person.surname:
                return Response(
                    {"message": "Unauthorized: User does not belong to your surname"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if person.flag_show:
                return Response(
                    {"message": "User Already Approved"},
                    status=status.HTTP_202_ACCEPTED,
                )
            flag_show = request.data.get("flag_show", person.flag_show)
            person.flag_show = flag_show
            person.save()
            serializer = PersonGetV4Serializer(person)
            return Response({"data": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"An unexpected error occurred: {str(e)}")
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    def delete(self, request):
        lang = request.data.get("lang", "en")
        try:
            admin_user_id = request.data.get("admin_user_id")
            if not admin_user_id or admin_user_id is None or admin_user_id == "":
                if lang == "guj":
                    return Response(
                        {"message": "એડમીન સભ્ય ડેટામાં મળી રહીયો નથી"},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                else:
                    return Response(
                        {"message": "Missing Admin User in request data"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            try:
                admin_person = get_person_queryset(request).get(pk=admin_user_id)
            except Person.DoesNotExist:
                return Response(
                    {"message": f"Admin Person not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if not admin_person.is_admin:
                if lang == "guj":
                    return Response(
                        {"message": "વપરાશકર્તા સભ્ય પાસે એડમિન એક્સેસ નથી"},
                        status=status.HTTP_200_OK,
                    )
                else:
                    return Response(
                        {"message": "User does not have admin access"},
                        status=status.HTTP_200_OK,
                    )

            # Cross-validate X-Mobile-Number header
            mobile_header = request.headers.get("X-Mobile-Number")
            if mobile_header:
                if (
                    admin_person.mobile_number1 != mobile_header
                    and admin_person.mobile_number2 != mobile_header
                ):
                    return Response(
                        {"message": "Unauthorized: Mobile number does not match admin user"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            user_id = request.data.get("user_id")
            if not user_id or user_id is None or user_id == "":
                return Response(
                    {"message": "Missing User in request data"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            try:
                person = get_person_queryset(request).get(pk=user_id)
            except Person.DoesNotExist:
                return Response(
                    {"message": f"Person not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            try:
                translate_person = TranslatePerson.objects.get(
                    person_id=user_id, is_deleted=False
                )
                translate_person.is_deleted = True
                translate_person.save()
            except TranslatePerson.DoesNotExist:
                pass
            try:
                top_member_ids = Surname.objects.filter(
                    name=person.surname
                ).values_list("top_member", flat=True)
                top_member_ids = [int(id) for id in top_member_ids]
                if len(top_member_ids) > 0:
                    children = get_relation_queryset(request).filter(
                        parent_id=user_id, is_deleted=False
                    )
                    for child in children:
                        child.parent_id = top_member_ids[0]
                        child.save()
                try:
                    child_data = get_relation_queryset(request).get(
                        child_id=user_id, is_deleted=False
                    )
                    child_data.is_deleted = True
                    child_data.save()
                except:
                    pass
            except Surname.DoesNotExist:
                return Response(
                    {"message": f"Surname not exist"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            except Exception as exp:
                return Response(
                    {"message": f"${exp}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            person.flag_show = False
            person.is_deleted = True
            person.save()
            return Response(
                {"message": f"Person deleted successfully."}, status=status.HTTP_200_OK
            )
        except Http404:
            return Response(
                {"message": f"Person not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": f"Failed to delete the record"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
class PersonBySurnameViewV4(APIView):
    def post(self, request):
        surname = request.data.get("surname")
        lang = request.data.get("lang", "en")
        is_father_selection = str(request.data.get("is_father_selection", "")).lower()
        mobile_header = request.headers.get("X-Mobile-Number")
 
        if not surname:
            message = "અટક જરૂરી છે" if lang == "guj" else "Surname ID is required"
            return JsonResponse({"message": message, "data": []}, status=400)
 
        # Base queryset — demo-aware
        queryset = get_person_queryset(request).filter(surname__id=surname, flag_show=True)
 
        # Filter by Samaj if mobile header is provided
        if mobile_header:
            try:
                request_person = get_person_queryset(request).filter(
                    Q(mobile_number1=mobile_header) | Q(mobile_number2=mobile_header),
                    is_deleted=False
                ).first()
                if request_person and request_person.samaj:
                    queryset = queryset.filter(samaj=request_person.samaj)
            except Exception:
                pass
 
        from django.db.models import Subquery, OuterRef
        
        trans_first_name_sq = Subquery(
            TranslatePerson.objects.filter(
                person_id=OuterRef("pk"),
                language=lang,
                is_deleted=False
            ).values("first_name")[:1]
        )
        trans_middle_name_sq = Subquery(
            TranslatePerson.objects.filter(
                person_id=OuterRef("pk"),
                language=lang,
                is_deleted=False
            ).values("middle_name")[:1]
        )

        persons_qs = (
            queryset.exclude(
                id__in=Surname.objects.exclude(
                    top_member__in=["", None]
                ).annotate(
                    top_member_as_int=Cast("top_member", IntegerField())
                ).values_list("top_member_as_int", flat=True)
            )
            .select_related("surname")
            .annotate(
                trans_fname=trans_first_name_sq,
                trans_mname=trans_middle_name_sq
            )
            .distinct()
            .values(
                "id",
                "first_name",
                "trans_fname",
                "middle_name",
                "trans_mname",
                "date_of_birth",
                "mobile_number1",
                "mobile_number2",
                "flag_show",
                "profile",
                "is_admin",
                "surname",
                "surname__name",
                "surname__guj_name",
                "thumb_profile",
            )
        )
 
        if is_father_selection != "true":
            persons_qs = persons_qs.filter(
                Q(mobile_number1__isnull=False) | Q(mobile_number2__isnull=False)
            ).exclude(mobile_number1="")
 
        if persons_qs.exists():
            persons_list = list(persons_qs)
            
            # Sort manually to avoid grouping/re-triggering distinct inside order_by
            if lang == "en":
                persons_list.sort(key=lambda x: (x.get("first_name") or "", x.get("middle_name") or ""))
            else:
                persons_list.sort(key=lambda x: (x.get("trans_fname") or "", x.get("trans_mname") or ""))

            for person in persons_list:
                # Swap the values between first_name and middle_name
                if lang != "en":
                    person["surname"] = person.pop("surname__guj_name", person.get("surname"))
                    person.pop("surname__name", None)
                    
                    person["trans_first_name"] = person.get("first_name")
                    person["trans_middle_name"] = person.get("middle_name")
                    
                    person["first_name"] = person.pop("trans_fname", None) or person.get("first_name")
                    person["middle_name"] = person.pop("trans_mname", None) or person.get("middle_name")
                else:
                    person["surname"] = person.pop("surname__name", person.get("surname"))
                    person.pop("surname__guj_name", None)
                    
                    person["trans_first_name"] = person.pop("trans_fname", None)
                    person["trans_middle_name"] = person.pop("trans_mname", None)

                if (
                    person.get("profile")
                    and str(person["profile"]) not in ("null", "")
                ):
                    person["profile"] = f"/media/{(person['profile'])}"
                else:
                    person["profile"] = os.getenv("DEFAULT_PROFILE_PATH")
                    
                if (
                    person.get("thumb_profile")
                    and str(person["thumb_profile"]) not in ("null", "")
                ):
                    person["thumb_profile"] = f"/media/{(person['thumb_profile'])}"
                else:
                    person["thumb_profile"] = os.getenv("DEFAULT_PROFILE_PATH")

            return JsonResponse({"data": persons_list}, status=200)
 
        return JsonResponse({"data": []}, status=200)
        
from rest_framework.parsers import MultiPartParser, FormParser

class CSVUploadAPIView(APIView):
    authentication_classes = []
    permission_classes = []
    parser_classes = [MultiPartParser, FormParser]

    def clean_val(self, val):
        if not val:
            return ""
        val = str(val).strip()
        # Remove Excel formula wrapper ="value"
        if val.startswith('="') and val.endswith('"'):
            return val[2:-1]
        # Remove single quote prefix
        if val.startswith("'"):
            return val[1:]
        return val

    @swagger_auto_schema(
        operation_description="Upload members via CSV/XLSX with strict location matching. Supports Dashboard sheet for referral codes.",
        manual_parameters=[
            openapi.Parameter('file', openapi.IN_FORM, type=openapi.TYPE_FILE, description="CSV or XLSX File", required=True)
        ],
        responses={200: "Processed successfully", 400: "Invalid data"}
    )
    def post(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        result = CSVImportService.process_file(uploaded_file, request=request)
        
        if "error" in result:
            return Response({"error": result["error"]}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": f"Processed successfully. Created {result['created']} and updated {result['updated']} entries.",
            "created": result['created'],
            "updated": result['updated'],
            "bug_file": result['bug_file_url']
        }, status=status.HTTP_200_OK)
    
class V4BannerDetailView(APIView):
    def get(self, request):
        lang = request.GET.get("lang", "en")
        today = datetime.now().date()

        # Auto-expire banners past their date
        Banner.objects.filter(
            expire_date__lt=today, is_active=True, is_deleted=False
        ).update(is_active=False)

        # Cross-validate X-Mobile-Number header and filter by samaj
        mobile_header = request.headers.get("X-Mobile-Number")
        samaj_id = None
        login_person = None

        if mobile_header:
            login_person = get_person_queryset(request).filter(
                Q(mobile_number1=mobile_header) | Q(mobile_number2=mobile_header),
                is_deleted=False
            ).select_related("samaj").first()

            if not login_person:
                return Response(
                    {"message": "Person not found for provided mobile number"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            samaj_id = login_person.samaj_id

        # Base banner querysets
        active_qs = Banner.objects.filter(
            is_active=True, expire_date__gte=today, is_deleted=False
        )
        expire_qs = Banner.objects.filter(
            is_active=False, expire_date__lt=today, is_deleted=False
        )

        # Apply filters based on admin status
        if login_person:
            if login_person.is_admin:
                # Admin sees all banners within their samaj
                if samaj_id:
                    active_qs = active_qs.filter(created_person__samaj_id=samaj_id)
                    expire_qs = expire_qs.filter(created_person__samaj_id=samaj_id)
            else:
                # Regular user sees only the banners they created
                active_qs = active_qs.filter(created_person=login_person)
                expire_qs = expire_qs.filter(created_person=login_person)
        elif samaj_id:
            active_qs = active_qs.filter(created_person__samaj_id=samaj_id)
            expire_qs = expire_qs.filter(created_person__samaj_id=samaj_id)

        active_banner = active_qs.order_by("expire_date")
        expire_banner = expire_qs.order_by("-expire_date")

        active_banner_data = BannerGETSerializer(active_banner, many=True).data
        expire_banner_data = BannerGETSerializer(expire_banner, many=True).data
        is_random_banner_qs = RandomBanner.objects.filter(samaj_id=samaj_id) if samaj_id else RandomBanner.objects.filter(samaj__isnull=True)
        is_random_banner = is_random_banner_qs.values_list(
            "is_random_banner", flat=True
        ).first()

        return Response(
            {
                "is_random_banner": is_random_banner,
                "Current Banner": active_banner_data,
                "Expire Banner": expire_banner_data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        today = datetime.now().date()
        images = request.FILES.getlist("images")
        created_person = int(request.data.get("created_person"))
        person = get_object_or_404(Person, id=created_person)

        # Cross-validate X-Mobile-Number header
        mobile_header = request.headers.get("X-Mobile-Number")
        if mobile_header:
            if (
                person.mobile_number1 != mobile_header
                and person.mobile_number2 != mobile_header
            ):
                return Response(
                    {"message": "Unauthorized: Mobile number does not match created_person"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        person = person.id
        expire_days = request.data.get("expire_days", 0)
        is_ad_lable = True
        if "is_ad_lable" in request.data:
            is_ad_lable = request.data.get("is_ad_lable").lower()
            if is_ad_lable == "true":
                is_ad_lable = True
            else:
                is_ad_lable = False

        if not expire_days:
            return Response(
                {"message": "Please enter expire_days"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            expire_days = int(expire_days)
        except ValueError:
            return Response(
                {"message": "Please enter a valid number for expire_days"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(images) != 1:
            return Response(
                {"message": "Please upload exactly one image"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        expire_date = today + timedelta(days=expire_days)

        serializer = BannerSerializer(
            data={
                "images": images[0],  # Use the single image
                "redirect_url": request.data.get("redirect_url"),
                "expire_date": expire_date,
                "created_person": person,
                "is_ad_lable": is_ad_lable,
            }
        )

        try:
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request, pk):
        banner_id = request.data.get("banner_id")
        if not banner_id:
            return Response(
                {"message": "Please enter Banner Details"},
                status=status.HTTP_400_BAD_REQUEST,
            )
 
        banner = get_object_or_404(Banner, id=banner_id)
 
        # Validate created_person — must match the banner's original creator
        created_person_id = request.data.get("created_person")
        if not created_person_id:
            return Response(
                {"message": "created_person is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if int(created_person_id) != banner.created_person_id:
            return Response(
                {"message": "Unauthorized: created_person does not match banner creator"},
                status=status.HTTP_403_FORBIDDEN,
            )
 
        # Cross-validate X-Mobile-Number header — caller must be the banner creator
        # If the header is present, enforce it matches one of the creator's numbers.
        # If the creator has no mobile numbers, return a clear 403 message.
        mobile_header = request.headers.get("X-Mobile-Number")
        if mobile_header:
            creator = banner.created_person
            creator_m1 = getattr(creator, "mobile_number1", None)
            creator_m2 = getattr(creator, "mobile_number2", None)
            # Log values to help debugging (will appear in journal)
            logger.info(
                "Banner delete attempt: banner_id=%s incoming_mobile=%s creator_m1=%s creator_m2=%s",
                pk,
                mobile_header,
                creator_m1,
                creator_m2,
            )
            if not creator_m1 and not creator_m2:
                return Response(
                    {"message": "Unauthorized: banner creator has no mobile number on record"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if mobile_header != (creator_m1 or "") and mobile_header != (creator_m2 or ""):
                return Response(
                    {"message": "Unauthorized: Mobile number does not match banner creator"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        images = request.FILES.getlist("images")
        expire_days = request.data.get("expire_days", 0)
        redirect_url = request.data.get("redirect_url")
        if images:
            if len(images) != 1:
                return Response(
                    {"message": "Please upload exactly one image"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            banner.images = images[0]
 
        if redirect_url is not None:
            banner.redirect_url = redirect_url
 
        if expire_days:
            try:
                expire_days = int(expire_days)
                banner.expire_date = datetime.now().date() + timedelta(days=expire_days)
                banner.is_active = True
            except ValueError:
                return Response(
                    {"message": "Please enter a valid number for expire_days"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if "is_ad_lable" in request.data:
            is_ad_lable = request.data.get("is_ad_lable").lower()
            if is_ad_lable == "true":
                is_ad_lable = True
            else:
                is_ad_lable = False
            banner.is_ad_lable = is_ad_lable
 
        try:
            banner.save()
            return Response({"message": "Your Banner Data is Successfully Updated"})
        except Exception as error:
            return Response({"message": str(error)}, status=status.HTTP_400_BAD_REQUEST)
 
    def delete(self, request, pk):
        try:
            banner = Banner.objects.get(pk=pk)
        except Banner.DoesNotExist:
            return Response(
                {"message": f"Banner record with ID {pk} does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"message": f"Failed to fetch Banner record: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
 
        # Cross-validate X-Mobile-Number header — caller must be the banner creator
        mobile_header = request.headers.get("X-Mobile-Number")
        if mobile_header:
            creator = banner.created_person
            creator_m1 = getattr(creator, "mobile_number1", None)
            creator_m2 = getattr(creator, "mobile_number2", None)
            # Log values to help debugging (will appear in journal)
            logger.info(
                "Banner delete attempt: banner_id=%s incoming_mobile=%s creator_m1=%s creator_m2=%s",
                pk,
                mobile_header,
                creator_m1,
                creator_m2,
            )
            if not creator_m1 and not creator_m2:
                return Response(
                    {"message": "Unauthorized: banner creator has no mobile number on record"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if mobile_header != (creator_m1 or "") and mobile_header != (creator_m2 or ""):
                return Response(
                    {"message": "Unauthorized: Mobile number does not match banner creator"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        try:
            if banner.is_deleted == False:
                banner.is_active = False
                banner.is_deleted = True
                banner.save()
                return Response(
                    {"message": f"Banner record ID {pk} deleted successfully."},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"message": f"Banner record ID {pk} already deleted."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        except Exception as e:
            return Response(
                {"message": f"Failed to delete the Banner record: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class V4RandomBannerView(APIView):
    def post(self, request):
        mobile_header = request.headers.get("X-Mobile-Number")
        if not mobile_header:
            return Response({"message": "X-Mobile-Number header is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            admin_person = get_person_queryset(request).get(Q(mobile_number1=mobile_header) | Q(mobile_number2=mobile_header))
            if not admin_person.is_admin:
                return Response({"message": "Unauthorized: Admin access required"}, status=status.HTTP_403_FORBIDDEN)
        except Person.DoesNotExist:
            return Response({"message": "Unauthorized: Admin person not found"}, status=status.HTTP_403_FORBIDDEN)

        is_random_banner = False
        if "is_random_banner" in request.data:
            is_random_banner = request.data.get("is_random_banner").lower()
            if is_random_banner == "true":
                is_random_banner = True
            else:
                is_random_banner = False
        try:
            data = RandomBanner.objects.filter(samaj_id=admin_person.samaj_id).first()
            if data:
                data.is_random_banner = is_random_banner
                data.save()
                return Response(
                    {"message": "data Successfully updated"}, status=status.HTTP_200_OK
                )
            else:
                RandomBanner.objects.create(is_random_banner=is_random_banner, samaj_id=admin_person.samaj_id)
                return Response(
                    {"message": "data Successfully created"},
                    status=status.HTTP_201_CREATED,
                )
        except Exception as error:
            return Response({"message": f"{error}"}, status=status.HTTP_400_BAD_REQUEST)

def append_to_log(filename, message):
    """Append a message to an existing log file, creating the file if it doesn't exist."""
    with open(filename, "a") as file:
        file.write(message + "\n")

class V4ProfileDetailView(APIView):

    def post(self, request):
        person_id = request.data.get("id", None)

        try:
            size = (300, 300)
            quality = 60
            if person_id:
                person = get_object_or_404(Person, pk=person_id)
                if person.profile != "":
                    person.profile.delete()
                    person.thumb_profile.delete()
                serializer = ProfileSerializer(person, data=request.data)
            else:
                serializer = ProfileSerializer(data=request.data)

            serializer.is_valid(raise_exception=True)
            serializer_data = serializer.save()

            if "profile" in request.FILES:
                thumb_img = compress_image(
                    serializer_data.profile,
                    serializer_data.thumb_profile,
                    size,
                    quality,
                )

            if person_id:
                return Response(
                    {"success": "Profile data updated successfully!"},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"success": "Profile data saved successfully!"},
                    status=status.HTTP_201_CREATED,
                )

        except Person.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error saving profile: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def delete(self, request):
        person_id = request.data.get("id", None)

        try:
            size = (300, 300)
            quality = 60
            if person_id:
                person = get_object_or_404(Person, pk=person_id)
                if person.profile != "":
                    person.profile.delete()
                    person.thumb_profile.delete()

            if person_id:
                return Response(
                    {"success": "Profile data remove successfully!"},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"success": "Person record not found!"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        except Person.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error removing profile: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
# class V4PersonDetailView(APIView):
#     authentication_classes = []
#     def get(self, request, pk):
#         try:
#             person = Person.objects.get(id=pk)
#             if person:
#                 lang = request.GET.get('lang', 'en')
#                 person = PersonGetSerializer(person, context={'lang': lang}).data
#                 person['child'] = []
#                 person['parent'] = {}
#                 person['brother'] = []
#                 child_data = ParentChildRelation.objects.filter(parent=int(person["id"]))
#                 if child_data.exists():
#                     child_data = GetParentChildRelationSerializer(child_data, many=True, context={'lang': lang}).data
#                     for child in child_data:
#                         person['child'].append(child.get("child"))
#                 parent_data = ParentChildRelation.objects.filter(child=int(person["id"])).first()
#                 if parent_data:
#                     parent_data = GetParentChildRelationSerializer(parent_data, context={'lang': lang}).data
#                     person['parent'] = parent_data.get("parent")
#                     brother_data = ParentChildRelation.objects.filter(parent=int(parent_data.get("parent").get("id", 0)))
#                     if brother_data.exists():
#                         brother_data = GetParentChildRelationSerializer(brother_data, many=True, context={'lang': lang}).data
#                         for brother in brother_data:
#                             if int(person["id"]) != int(brother["child"]["id"]) :
#                                 person['brother'].append(brother.get("child"))
#                 return Response(person, status=status.HTTP_200_OK)
#         except Person.DoesNotExist:
#             return Response({'error': 'Person not found'}, status=status.HTTP_404_NOT_FOUND)
        
#     def post(self, request):
#         surname = request.data.get('surname', 0)
#         if not surname:
#             surname = 0
#         persons_surname_wise = Surname.objects.filter(Q(id=int(surname))).first()
#         father = request.data.get('father', 0)        
#         top_member = 0
#         if persons_surname_wise: 
#             top_member = int(GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0))
#             if father == 0 :
#                 father = top_member
#         children = request.data.get('child', [])
#         first_name = request.data.get('first_name')
#         middle_name = request.data.get('middle_name')
#         address = request.data.get('address')
#         out_of_address = request.data.get('out_of_address')
#         lang = request.data.get('lang', 'en')
#         date_of_birth = request.data.get('date_of_birth')
#         blood_group = request.data.get('blood_group', 1)
#         city = request.data.get('city')
#         state = request.data.get('state')
#         out_of_country = request.data.get('out_of_country', 1)
#         if (int(out_of_country) == 0) :
#             out_of_country = 1
#         flag_show = request.data.get('flag_show')
#         mobile_number1 = request.data.get('mobile_number1')
#         mobile_number2 = request.data.get('mobile_number2')
#         status_name = request.data.get('status')
#         is_admin = request.data.get('is_admin')
#         is_registered_directly = request.data.get('is_registered_directly')
#         samaj = request.data.get('samaj')
#         # Auto-derive samaj from the surname if not explicitly provided
#         if not samaj and persons_surname_wise and persons_surname_wise.samaj:
#             samaj = persons_surname_wise.samaj.id
#         person_data = {
#             'first_name': first_name,
#             'middle_name': middle_name,
#             'address': address,
#             'out_of_address': out_of_address,
#             'date_of_birth': date_of_birth,
#             'blood_group': blood_group,
#             'city': city,
#             'state': state,
#             'out_of_country': out_of_country,
#             'flag_show': flag_show,
#             'mobile_number1': mobile_number1,
#             'mobile_number2': mobile_number2,
#             'status': status_name,
#             'surname': surname if surname else None,
#             'is_admin': is_admin,
#             'is_registered_directly': is_registered_directly,
#             'samaj': samaj,
#         }
#         serializer = PersonSerializer(data=person_data)
#         if serializer.is_valid():
#             if len(children) > 0 :
#                 children_exist = ParentChildRelation.objects.filter(child__in=children)
#                 if children_exist.exclude(parent=top_member).exists():
#                     return JsonResponse({'message': 'Children already exist'}, status=400)
#                 children_exist.filter(parent=top_member).delete()
#             persons = serializer.save()
#             try:
#                 if not first_name:
#                     raise ValueError("first_name is required")
#                 user, user_created = User.objects.get_or_create(username=first_name)
#                 if user_created:
#                     user.set_password(''.join(choices(string.ascii_letters + string.digits, k=12)))
#                 user.save()
#                 if user_created:
#                     print(f"New user created: {user.username}")
#                 else:
#                     print(f"User updated (username): {user.username}")
#             except IntegrityError as e:
#                 # Handle potential duplicate username or other database integrity errors
#                 print(f"IntegrityError encountered: {e}")
#             parent_serializer = ParentChildRelationSerializer(data={
#                                 'parent': father, 
#                                 'child': persons.id,
#                                 'created_user': persons.id
#                             })
#             if parent_serializer.is_valid():
#                 parent_serializer.save()
#             for child in children :
#                 child_serializer = ParentChildRelationSerializer(data={
#                                 'child': child, 
#                                 'parent': persons.id,
#                                 'created_user': persons.id
#                             })
#                 if child_serializer.is_valid():
#                     child_serializer.save()
#             if (lang != "en") :   
#                 person_translate_data = {
#                     'first_name': first_name, 
#                     'person_id': persons.id,
#                     'middle_name': middle_name,
#                     'address': address,
#                     'out_of_address':out_of_address,

#                     'language': lang
#                 }
#                 person_translate_serializer = TranslatePersonSerializer(data=person_translate_data)
#                 if person_translate_serializer.is_valid():
#                     person_translate_serializer.save()
#             return Response(PersonGetSerializer(persons, context={'lang': lang}).data, status=status.HTTP_201_CREATED)
#         else:
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
#     def put(self, request, pk):
#         person = get_object_or_404(Person, pk=pk)
#         if not person:
#             return JsonResponse({'message': 'Person not found'}, status=status.HTTP_400_BAD_REQUEST)
#         surname = request.data.get('surname', 0)
#         persons_surname_wise = Surname.objects.filter(Q(id=int(surname))).first()
#         father = request.data.get('father', 0) 
#         top_member = 0
#         if persons_surname_wise: 
#             top_member = int(GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0))
#             if father == 0:
#                 father = top_member
#         children = request.data.get('child', [])
#         first_name = request.data.get('first_name')
#         middle_name = request.data.get('middle_name')
#         address = request.data.get('address')
#         out_of_address = request.data.get('out_of_address')
#         lang = request.data.get('lang', 'en')
#         date_of_birth = request.data.get('date_of_birth')
#         blood_group = request.data.get('blood_group', 1)
#         city = request.data.get('city')
#         state = request.data.get('state')
#         out_of_country = request.data.get('out_of_country', 1)
#         if (int(out_of_country) == 0) :
#             out_of_country = 1
#         flag_show = request.data.get('flag_show')
#         mobile_number1 = request.data.get('mobile_number1')
#         mobile_number2 = request.data.get('mobile_number2')
#         status_name = request.data.get('status')
#         is_admin = request.data.get('is_admin')
#         is_registered_directly = request.data.get('is_registered_directly')
#         person_data = {
#             'first_name' : person.first_name if lang == 'en' else first_name,
#             'middle_name' : person.middle_name if lang == 'en' else middle_name,
#             'address' : person.address if lang == 'en' else address,
#             'out_of_address': out_of_address,
#             'date_of_birth': date_of_birth,
#             'blood_group': blood_group,
#             'city': city,
#             'state': state,
#             'out_of_country': out_of_country,
#             'flag_show': flag_show,
#             'mobile_number1': mobile_number1,
#             'mobile_number2': mobile_number2,
#             'status': status_name,
#             'surname': surname,
#             'is_admin': is_admin,
#             'is_registered_directly': is_registered_directly
#         }

#         ignore_fields = ['update_field_message', 'id', 'flag_show', 'is_admin', 'is_registered_directly']
#         update_field_message = []
#         for field, new_value in person_data.items():
#             if field in ignore_fields:
#                 continue
#             old_value = getattr(person, field, None)

#             if hasattr(old_value, 'id'):
#                 old_value = old_value.id

#             if old_value != new_value:
#                 update_field_message.append({
#                     'field': field,
#                     'previous': old_value,
#                     'new': new_value
#                 })

#         if update_field_message:
#             person.update_field_message = str(update_field_message)
            
#         serializer = PersonSerializer(person, data=person_data, context={'person_id': person.id})
#         if serializer.is_valid():
#             if len(children) > 0:
#                 children_exist = ParentChildRelation.objects.filter(child__in=children)
#                 if children_exist.exclude(parent=top_member).exclude(parent=person.id).exists():
#                     return JsonResponse({'message': 'Children already exist'}, status=400)
#             persons = serializer.save()

#             father_data = ParentChildRelation.objects.filter(child=persons.id)
#             data = { 
#                     'parent': father, 
#                     'child': persons.id,
#                     'created_user': persons.id
#                 }
#             father_data_serializer = None
#             if father_data.exists() :
#                 father_data = father_data.first()
#                 father_data_serializer = ParentChildRelationSerializer(father_data, data=data)
#             else :
#                 father_data_serializer = ParentChildRelationSerializer(data=data)
#             if father_data_serializer.is_valid():
#                 father_data_serializer.save()
#             for child in children:
#                 child_data = ParentChildRelation.objects.filter(child=child)
#                 data = { 
#                     'child': child, 
#                     'parent': persons.id,
#                     'created_user': persons.id
#                 }
#                 child_data_serializer = None
#                 if child_data.exists() :
#                     child_data = child_data.first()
#                     child_data_serializer = ParentChildRelationSerializer(child_data, data=data)
#                 else :
#                     child_data_serializer = ParentChildRelationSerializer(data=data)
#                 if child_data_serializer.is_valid():
#                     child_data_serializer.save()
#             if len(children) > 0:       
#                 remove_child_person = ParentChildRelation.objects.filter(parent=persons.id).exclude(child__in=children)
#                 if remove_child_person.exists():
#                     for child in remove_child_person:
#                         child.parent_id = int(top_member)
#                         child.save()
#             if (lang != "en"):
#                 lang_data = TranslatePerson.objects.filter(person_id=persons.id).filter(language=lang)
#                 if lang_data.exists() :
#                     lang_data = lang_data.first()
#                     person_translate_data = {
#                         'first_name': first_name,
#                         'middle_name': middle_name,
#                         'address': address,
#                         'out_of_address':out_of_address,
#                         'language': lang
#                     }
#                     person_translate_serializer = TranslatePersonSerializer(lang_data, data=person_translate_data)
#                     if person_translate_serializer.is_valid():
#                         person_translate_serializer.save()
#             return Response({
#                 "person": PersonGetSerializer(persons, context={'lang': lang}).data
#             }, status=status.HTTP_200_OK)
#         else:
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     def delete(self, request, pk):
#         person = get_object_or_404(Person, pk=pk)
#         try:
#             person.delete()
#             return Response({"message": "Person record deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
#         except Exception as e:
#             return Response({"message": f"Failed to delete the person record: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class V4CountryWiseSummaryAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_description="Get a summary of out-of-country members grouped by country. Restricted by user's samaj.",
        manual_parameters=[
            openapi.Parameter('X-Mobile-Number', openapi.IN_HEADER, description="User Mobile Number", type=openapi.TYPE_STRING, required=True),
        ],
        responses={200: openapi.Response(
            description="Summary list of countries with member counts",
            schema=openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'country_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'country_name': openapi.Schema(type=openapi.TYPE_STRING),
                        'flag': openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
                        'total_members': openapi.Schema(type=openapi.TYPE_INTEGER)
                    }
                )
            )
        )}
    )
    def get(self, request):
        lang = request.GET.get("lang", "en")
        mobile_number = request.headers.get("X-Mobile-Number")
        if not mobile_number:
            return Response({"error": "Mobile number is required"}, status=status.HTTP_400_BAD_REQUEST)

        login_person = get_person_queryset(request).filter(
            Q(mobile_number1=mobile_number) | Q(mobile_number2=mobile_number),
        ).first()

        if not login_person:
            return Response({"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND)

        if not login_person.samaj_id:
            return Response({"error": "Samaj not assigned to this user"}, status=status.HTTP_400_BAD_REQUEST)

        # Base queryset: Out of country (not India or empty), flag_show=True, not deleted
        base_qs = get_person_queryset(request).filter(
            flag_show=True,
            samaj_id=login_person.samaj_id
        ).exclude(
            Q(out_of_country__name__iexact='India') | Q(out_of_country__name__exact='') | Q(out_of_country__isnull=True)
        )
        
        summary_qs = base_qs.values(
            country_id=F('out_of_country__id'),
            country_name=F('out_of_country__name'),
            guj_name=F('out_of_country__guj_name'),
            flag=F('out_of_country__flag')
        ).annotate(
            total_members=Count('id')
        ).order_by('-total_members', 'country_name')

        from ..serializers import CountrySummarySerializer
        serializer = CountrySummarySerializer(summary_qs, many=True, context={'lang': lang})
        return Response(serializer.data, status=status.HTTP_200_OK)


class V4CountryWiseMembersAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_description="Get members for a specific country restricted by user's samaj.",
        manual_parameters=[
            openapi.Parameter('lang', openapi.IN_QUERY, description="Language (en/guj)", type=openapi.TYPE_STRING),
            openapi.Parameter('X-Mobile-Number', openapi.IN_HEADER, description="User Mobile Number", type=openapi.TYPE_STRING, required=True),
        ],
        responses={200: openapi.Response(description="List of members in the country", schema=CountryWiseMemberSerializer(many=True))}
    )
    def get(self, request, country_id):
        lang = request.GET.get("lang", "en")
        mobile_number = request.headers.get("X-Mobile-Number")
        
        if not mobile_number:
            return Response({"error": "Mobile number is required"}, status=status.HTTP_400_BAD_REQUEST)

        login_person = get_person_queryset(request).filter(
            Q(mobile_number1=mobile_number) | Q(mobile_number2=mobile_number),
        ).first()

        if not login_person:
            return Response({"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND)

        if not login_person.samaj_id:
            return Response({"error": "Samaj not assigned to this user"}, status=status.HTTP_400_BAD_REQUEST)

        # Base queryset: specific country, show true, not deleted, same samaj
        members = get_person_queryset(request).filter(
            flag_show=True,
            out_of_country_id=country_id,
            samaj_id=login_person.samaj_id
        ).select_related(
            "surname", "samaj", "samaj__village", "samaj__village__taluka", "samaj__village__taluka__district", "city", "state", "out_of_country"
        ).order_by("first_name")

        from ..serializers import CountryWiseMemberSerializer
        serializer = CountryWiseMemberSerializer(members, many=True, context={"lang": lang})
        return Response({"data": serializer.data}, status=status.HTTP_200_OK)

class CityDetailView(APIView):
    authentication_classes = []
    def get(self, request, state_id):
        try:
            state = State.objects.prefetch_related('state').get(id=state_id)
        except State.DoesNotExist:
            return Response({'error': 'State not found'}, status=status.HTTP_404_NOT_FOUND)
        state = state.state.all()
        lang = request.GET.get('lang', 'en')
        serializer = CitySerializer(state, many=True, context={'lang': lang})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class StateDetailView(APIView):
    authentication_classes = []
    def get(self, request):
        state = State.objects.all()
        lang = request.GET.get('lang', 'en')
        serializer = StateSerializer(state, many=True, context={'lang': lang})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class CountryDetailView(APIView):
    authentication_classes = []
    def get(self, request):
        country = Country.objects.all()
        lang = request.GET.get('lang', 'en')
        serializer = CountrySerializer(country, many=True, context={'lang': lang})
        data = sorted(serializer.data, key=lambda x: (x["name"]))
        return Response(data,  status=status.HTTP_200_OK)
    
class PersonMiddleNameUpdate(APIView):
    def put(self, request):
        top_member_ids = Surname.objects.values("top_member").values_list(
            "top_member", flat=True
        )
        top_member_ids = [int(id) for id in top_member_ids]
        allChild = get_relation_queryset(request).exclude(
            parent__id__in=top_member_ids, is_deleted=False
        ).order_by("id")
        if allChild and allChild.exists():
            for child in allChild:
                child.child.middle_name = child.parent.first_name
                child.child.save()

                traslate_child = TranslatePerson.objects.filter(
                    person_id=child.child, is_deleted=False
                ).first()
                traslate_parent = TranslatePerson.objects.filter(
                    person_id=child.parent, is_deleted=False
                ).first()
                if traslate_child and traslate_parent:
                    traslate_child.middle_name = traslate_parent.first_name
                    traslate_child.save()

        return JsonResponse({"data": "Okay"}, status=200)
    
class AdditionalData(APIView):
    def get(self, request):
        mobile_header = request.headers.get("X-Mobile-Number")
        if not mobile_header:
            return Response({"message": "X-Mobile-Number header is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        person_exists = get_person_queryset(request).filter(Q(mobile_number1=mobile_header) | Q(mobile_number2=mobile_header)).exists()
        if not person_exists:
            return Response({"message": "Unauthorized: Mobile number does not match any person"}, status=status.HTTP_403_FORBIDDEN)

        lang = request.GET.get("lang", "en")
        
        person = get_person_queryset(request).filter(Q(mobile_number1=mobile_header) | Q(mobile_number2=mobile_header)).first()
        samaj_id = person.samaj_id if person else None
        
        # Try to get samaj specific setting
        additional_data_entry = None
        if samaj_id:
            additional_data_entry = AdsSetting.objects.filter(samaj__id=samaj_id).values("ads_setting").first()
            
        # Fallback to global setting (samaj is null)
        if not additional_data_entry:
            additional_data_entry = AdsSetting.objects.filter(samaj__isnull=True).values("ads_setting").first()
            
        additional_data = (
            additional_data_entry["ads_setting"] if additional_data_entry else {}
        )
        return Response({"additional_data": additional_data}, status=status.HTTP_200_OK)
    
class V4SurnameDetailView(APIView):
    authentication_classes = []

    def get(self, request):
        person_id = request.GET.get("person_id")
        lang = request.GET.get("lang", "en")
        try:
            person = get_person_queryset(request).get(id=person_id, is_deleted=False)
        except:
            return Response(
                {"message": "Person Not Found"}, status=status.HTTP_404_NOT_FOUND
            )

        surnames = Surname.objects.all().order_by("fix_order")
        serializer = SurnameSerializer(surnames, many=True, context={"lang": lang})
        surname_data = serializer.data
        for index, instance in enumerate(surname_data):
            if instance["id"] == person.surname.id:
                instance["sort_no"] = 0
            else:
                instance["sort_no"] = 2
        surname_data = sorted(surname_data, key=lambda x: (x["sort_no"]))
        return Response(surname_data, status=status.HTTP_200_OK)

    def post(self, request):
        surname_serializer = SurnameSerializer(data=request.data)
        if surname_serializer.is_valid():
            surname_instance = surname_serializer.save()
            person_data = {
                "first_name": surname_instance.name,
                "middle_name": surname_instance.name,
                "address": "",
                "blood_group": 1,
                "date_of_birth": "1947-08-15 00:00:00.000",
                "out_of_country": 1,
                "out_of_address": "",
                "city": 1,
                "state": 1,
                "mobile_number1": "",
                "mobile_number2": "",
                "surname": surname_instance.id,
                "flag_show": True,
                "is_admin": False,
                "is_registered_directly": True,
            }
            person_serializer = PersonSerializer(data=person_data)
            if person_serializer.is_valid():
                person_instance = person_serializer.save()
                surname_instance.top_member = person_instance.id
                surname_instance.save()
                lang = request.data.get("lang", "en")
                if lang != "en":
                    guj_name = request.data.get(
                        "guj_name", request.data.get("name", "")
                    )
                    if guj_name:
                        person_translate_data = {
                            "first_name": guj_name,
                            "person_id": person_instance.id,
                            "middle_name": guj_name,
                            "address": "",
                            "out_of_address": "",
                            "language": lang,
                        }
                        person_translate_serializer = TranslatePersonSerializer(
                            data=person_translate_data
                        )
                        if person_translate_serializer.is_valid():
                            person_translate_instance = (
                                person_translate_serializer.save()
                            )
                            return Response(
                                {"surname": surname_serializer.data},
                                status=status.HTTP_201_CREATED,
                            )
                        else:
                            surname_instance.delete()
                            person_instance.delete()
                            return Response(
                                person_translate_serializer.errors,
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                return Response(
                    {"surname": surname_serializer.data}, status=status.HTTP_201_CREATED
                )
            else:
                surname_instance.delete()
                return Response(
                    person_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                )
        return Response(surname_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
def capitalize_name(name):
    return name.capitalize()
class FirstCapitalize(APIView):
    def get(self, request):
        lang = request.GET.get("lang", "en")
        person = Person.objects.all()
        for i in person:
            i.first_name = capitalize_name(i.first_name)
            i.middle_name = capitalize_name(i.middle_name)
            i.save()
        return Response({"okay"})
    
class BloodGroupDetailView(APIView):
    authentication_classes = []
    def get(self, request):
        lang = request.GET.get("lang", "en")
        bloodgroup = BloodGroup.objects.all()
        serializer = BloodGroupSerializer(bloodgroup, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class ChildPerson(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('X-Mobile-Number', openapi.IN_HEADER, description="User Mobile Number", type=openapi.TYPE_STRING, required=True),
        ]
    )
    def get(self, request):
        try:
            mobile_header = request.headers.get("X-Mobile-Number")
            if not mobile_header:
                return Response(
                    {"message": "X-Mobile-Number header is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            person_id = request.GET.get("parent_id")
            if not person_id:
                return Response({"message": "parent_id is required in query parameters"}, status=status.HTTP_400_BAD_REQUEST)
                
            lang = request.GET.get("lang", "en")
            child_ids = get_relation_queryset(request).filter(
                parent=int(person_id)
            ).values_list("child", flat=True)
            children = get_person_queryset(request).filter(id__in=child_ids, is_deleted=False)
            child_data = PersonGetSerializer(
                children, many=True, context={"lang": lang}
            )
            return Response({"child_data": child_data.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"child_data": [], "Error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('X-Mobile-Number', openapi.IN_HEADER, description="User Mobile Number", type=openapi.TYPE_STRING, required=True),
        ]
    )
    def post(self, request):
        try:
            print("Chiled -person -post --", request.data)
            mobile_header = request.headers.get("X-Mobile-Number")
            if not mobile_header:
                return Response(
                    {"message": "X-Mobile-Number header is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Fetch the logged-in user to dynamically determine is_demo
            login_person = Person.objects.filter(
                Q(mobile_number1=mobile_header) | Q(mobile_number2=mobile_header)
            ).first()
            
            if login_person:
                is_demo_user = login_person.is_demo
            else:
                # If person not found by mobile, default to false
                is_demo_user = False
            
            parent_id = request.data.get("parent_id")
            lang = request.data.get("lang", "en")
            name = request.data.get("child_name")
            dob = request.data.get("dob")
            mobile_number = request.data.get("mobile_number") or ""
            platform = request.data.get("platform")
            
            person_data = Person.objects.get(id=parent_id, is_deleted=False, is_demo=is_demo_user)
            person_create = Person.objects.create(
                first_name=name,
                middle_name=person_data.first_name,
                surname=person_data.surname,
                date_of_birth=dob,
                address=person_data.address,
                mobile_number1=mobile_number,
                mobile_number2="",
                out_of_address=person_data.out_of_address,
                city=person_data.city,
                state=person_data.state,
                samaj=person_data.samaj,
                out_of_country=person_data.out_of_country,
                is_out_of_country=person_data.is_out_of_country,
                is_demo=is_demo_user,
                child_flag=True,
                platform=platform,
                update_field_message='newly created as child'
            )
            person_child = ParentChildRelation.objects.create(
                parent=person_data, child=person_create, created_user=person_data, is_demo=is_demo_user
            )
            try:
                translate_data = TranslatePerson.objects.get(
                    person_id=parent_id, is_deleted=False
                )
                if translate_data is not None:
                    translate_data = TranslatePerson.objects.create(
                        person_id=person_create,
                        first_name=name,
                        middle_name=translate_data.first_name,
                        address=translate_data.address,
                        out_of_address=translate_data.out_of_address,
                        language="guj",
                    )
            except Exception as e:
                pass
            if lang == "guj":
                message = "તમારું બાળક સફળતાપૂર્વક અમારા સભ્યોમાં નોંધાયેલ છે. હવે તમે તમારા એડમિનનો સંપર્ક કરી શકો છો."
            else:
                message = "Your child is successfully registered in our members. Now you can contact your admin."
            return Response(
                {"message": message, "child_id": person_create.id},
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('X-Mobile-Number', openapi.IN_HEADER, description="User Mobile Number", type=openapi.TYPE_STRING, required=True),
        ]
    )
    def put(self, request):
        try:
            mobile_header = request.headers.get("X-Mobile-Number")
            if not mobile_header:
                return Response(
                    {"message": "X-Mobile-Number header is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            print("Chiled -person -put --", request.data)
            child_id = request.data.get("child_id")
            child_name = request.data.get("child_name")
            dob = request.data.get("dob")
            mobile_number = request.data.get("mobile_number")
            lang = request.data.get("lang", "en")
            person_data = get_person_queryset(request).get(id=child_id)
            if person_data:
                ignore_fields = ['first_name', 'date_of_birth', 'mobile_number1']
                update_field_message = []
                for field, new_value in request.data.items():
                    if field == 'child_name':
                        field = 'first_name'
                    elif field == 'dob':
                        field = 'date_of_birth'
                    elif field == 'mobile_number':
                        field = 'mobile_number1'
                    if field in ignore_fields:
                        old_value = getattr(person_data, field, None)
                        print("Old Value", old_value, "New Value", new_value, field)
                        if hasattr(old_value, 'id'):
                            old_value = old_value.id

                        if old_value != new_value:
                            update_field_message.append({
                                'field': field,
                                'previous': old_value,
                                'new': new_value
                            })

                if update_field_message:
                    person_data.update_field_message = str(update_field_message)
            
                existing_profile = person_data.profile
                person_data.first_name = child_name
                person_data.date_of_birth = dob
                person_data.mobile_number1 = mobile_number
                person_data.flag_show = False
                
                # Ensure structural fields stay in sync with the parent
                # relation_data = get_relation_queryset(request).filter(child=person_data, is_deleted=False).first()
                # if relation_data and relation_data.parent:
                #     parent_record = relation_data.parent
                #     person_data.samaj = parent_record.samaj
                #     person_data.out_of_country = parent_record.out_of_country
                #     person_data.is_out_of_country = parent_record.is_out_of_country
                #     person_data.is_demo = parent_record.is_demo
                    
                person_data.save()

                if "profile" in request.data:
                    new_profile = request.data["profile"]
                    person_data.profile = new_profile
                    person_data.save()

                if existing_profile and existing_profile != person_data.profile:
                    existing_profile.delete()

            return Response(
                {"child_id": child_id, "message": "succesfully updated"},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('X-Mobile-Number', openapi.IN_HEADER, description="User Mobile Number", type=openapi.TYPE_STRING, required=True),
        ]
    )
    def delete(self, request):
        try:
            mobile_header = request.headers.get("X-Mobile-Number")
            if not mobile_header:
                return Response(
                    {"message": "X-Mobile-Number header is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            lang = request.data.get("lang", "en")
            # child_id = request.data.get("child_id")
            child_id = request.data.get("child_id") or request.GET.get("child_id")
            person = get_person_queryset(request).get(id=child_id)
            topmember = Surname.objects.get(id=person.surname.id)
            topmaember_id = topmember.top_member

            # Fetch the top member Person instance (Bypass is_demo filter because topmember is strictly a real Person)
            top_member_person = Person.objects.filter(id=topmaember_id).first()

            parent_relation_data = get_relation_queryset(request).filter(
                parent=person, is_deleted=False
            )
            if parent_relation_data:
                for data in parent_relation_data:
                    # If the supreme top member got deleted from the system, gracefully soft-delete the orphan link instead of crashing
                    if top_member_person:
                        data.parent = top_member_person
                    else:
                        data.is_deleted = True
                    data.save()

            relation_data_qs = get_relation_queryset(request).filter(
            child=person, is_deleted=False
        )
            if relation_data_qs.exists():
                for relation_data in relation_data_qs:
                    relation_data.is_deleted = True
                    relation_data.save()

                person.flag_show = False
                person.is_deleted = True
                person.save()

                messages = {
                    "deleted_data": {
                        "en": "Your child is successfully deleted in members",
                        "guj": "તમારા બાળકને સભ્યોમાંથી સફળતાપૂર્વક કાઢી નાખવામાં આવ્યું છે",
                    },
                }
                return Response(
                    {"message": messages["deleted_data"][lang]}, status=status.HTTP_200_OK
                )
        except Exception as error:
            import traceback
            traceback.print_exc()
            return Response(
                {"message": f"Error: {str(error)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
