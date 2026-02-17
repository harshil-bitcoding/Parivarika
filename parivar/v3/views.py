from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..models import *
from ..serializers import *
from notifications.models import PersonPlayerId
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
from logging import getLogger
from django.conf import settings
import mimetypes
from django.http import Http404
from django.db.models import Case, When, F, Q, IntegerField
from django.db.models.functions import Coalesce, Cast
from rest_framework.status import (
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_200_OK,
    HTTP_401_UNAUTHORIZED,
)
import os
from django.db.models import Q
from datetime import datetime, timedelta
from django.core.files.uploadedfile import InMemoryUploadedFile


def updated_log(person_id, updated_history, created_person_id):
    try:
        # Fetch the Person instances
        person_instance = Person.objects.get(pk=person_id)
        created_person_instance = Person.objects.get(pk=created_person_id)

        # Create the log with the instances
        PersonUpdateLog.objects.create(
            person=person_instance,
            updated_history=updated_history,
            created_person=created_person_instance,
        )
        return Response({"message": "okay"}, status=status.HTTP_200_OK)
    except Person.DoesNotExist as e:
        return Response(
            {"error": "Person instance not found"}, status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response({"error": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)


class ParentChildRelationDetailViewV3(APIView):
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
            # Query
            queryset = (
                Person.objects.filter(surname__id=surnameid, is_deleted=False)
                .order_by("date_of_birth")
                .annotate(
                    translated_first_name=Case(
                        When(
                            Q(
                                translateperson__first_name__isnull=False,
                                translateperson__language=lang,
                            ),
                            then=F("translateperson__first_name"),
                        ),
                        default=F("first_name"),
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


class PersonBySurnameViewV3(APIView):
    def post(self, request):
        surname = request.data.get("surname")
        lang = request.data.get("lang", "en")
        is_father_selection = request.data.get("is_father_selection", "").lower()

        if not surname:
            message = "અટક જરૂરી છે" if lang == "guj" else "Surname ID is required"
            return JsonResponse({"message": message, "data": []}, status=400)

        persons = (
            Person.objects.filter(surname__id=surname, is_deleted=False, flag_show=True)
            .exclude(
                id__in=Surname.objects.annotate(
                    top_member_as_int=Cast("top_member", IntegerField())
                ).values_list("top_member_as_int", flat=True)
            )
            .select_related("surname")
            .prefetch_related("translateperson")
            .distinct()
            .values(
                "id",
                "first_name",
                "translateperson__first_name",
                "middle_name",
                "translateperson__middle_name",
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
            persons = persons.filter(
                Q(mobile_number1__isnull=False) | Q(mobile_number2__isnull=False)
            ).exclude(mobile_number1="")

        if persons.exists():
            persons = (
                persons.order_by("first_name", "middle_name")
                if lang == "en"
                else persons.order_by(
                    "translateperson__first_name", "translateperson__middle_name"
                )
            )
            # Execute the query and fetch results

            for person in persons:
                # Swap the values between first_name and middle_name
                if lang != "en":
                    person["surname"] = person["surname__guj_name"]
                    (
                        person["first_name"],
                        person["middle_name"],
                        person["trans_first_name"],
                        person["trans_middle_name"],
                    ) = (
                        person["translateperson__first_name"],
                        person["translateperson__middle_name"],
                        person["first_name"],
                        person["middle_name"],
                    )
                else:
                    person["surname"] = person["surname__name"]
                    person["trans_first_name"], person["trans_middle_name"] = (
                        person["translateperson__first_name"],
                        person["translateperson__middle_name"],
                    )
                if (
                    person["profile"]
                    and person["profile"] != "null"
                    and person["profile"] != ""
                ):
                    person["profile"] = f"/media/{(person['profile'])}"
                else:
                    person["profile"] = os.getenv("DEFAULT_PROFILE_PATH")
                if (
                    person["thumb_profile"]
                    and person["thumb_profile"] != "null"
                    and person["thumb_profile"] != ""
                ):
                    person["thumb_profile"] = f"/media/{(person['thumb_profile'])}"
                else:
                    person["thumb_profile"] = os.getenv("DEFAULT_PROFILE_PATH")
                person.pop("translateperson__first_name")
                person.pop("translateperson__middle_name")
                person.pop("surname__name")
                person.pop("surname__guj_name")

            results = list(persons)

            return JsonResponse({"data": results}, status=200)

        return JsonResponse({"data": []}, status=200)


class PersonMiddleNameUpdate(APIView):
    def put(self, request):
        top_member_ids = Surname.objects.values("top_member").values_list(
            "top_member", flat=True
        )
        top_member_ids = [int(id) for id in top_member_ids]
        allChild = ParentChildRelation.objects.exclude(
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


class SearchbyPerson(APIView):
    def post(self, request):
        lang = request.data.get("lang", "en")
        search = request.data.get("search", "")
        isAllSearch = request.data.get("is_all_search", "false")
        if search == "":
            return JsonResponse({"data": []}, status=200)

        search_keywords = search.split(" ")
        query = Q()
        for keyword in search_keywords:
            query &= (
                Q(first_name__icontains=keyword)
                | Q(date_of_birth__icontains=keyword)
                | Q(mobile_number1__icontains=keyword)
                | Q(mobile_number2__icontains=keyword)
                | Q(surname__name__icontains=keyword)
                | Q(surname__guj_name__icontains=keyword)
                | Q(translateperson__first_name__icontains=keyword)
            )

        query = Person.objects.filter(query, flag_show=True, is_deleted=False).exclude(
            id__in=Surname.objects.annotate(
                top_member_as_int=Cast("top_member", IntegerField())
            ).values_list("top_member_as_int", flat=True)
        )

        # if isAllSearch == "false":
        #     query = query.exclude(
        #         Q(mobile_number1__isnull=True) | Q(mobile_number1=""),
        #         Q(mobile_number2__isnull=True) | Q(mobile_number2=""),
        #     )

        query = (
            query.select_related("surname")
            .distinct()
            .order_by(
                "first_name",
                "translateperson__first_name",
                "middle_name",
                "translateperson__middle_name",
                "surname__name",
            )
        )

        # Serialize the results to JSON
        data = PersonGetDataSortSerializer(query, many=True, context={"lang": lang})
        return JsonResponse({"data": data.data}, status=200)


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
            flag_show=True, is_super_admin=True, is_deleted=False
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


class V3LoginAPI(APIView):

    def post(self, request):

        mobile_number = request.data.get("mobile_number")
        lang = request.data.get("lang", "en")
        player_id = request.data.get("player_id", "")
        is_ios_platform = request.data.get("is_ios_platform", False)

        if not mobile_number:
            error_message = (
                "મોબાઈલ નંબર જરૂરી છે" if lang == "guj" else "Mobile number is required"
            )
            return Response(
                {"message": error_message}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            person = Person.objects.get(
                Q(mobile_number1=mobile_number) | Q(mobile_number2=mobile_number),
                is_deleted=False,
            )

        except Person.DoesNotExist:
            error_message = "સભ્ય નોંધાયેલ નથી" if lang == "guj" else "Person not found"
            return Response(
                {"message": error_message}, status=status.HTTP_404_NOT_FOUND
            )

        available_platform = "Ios" if is_ios_platform == True else "Android"

        if player_id:
            try:
                player_person = PersonPlayerId.objects.get(player_id=player_id)
                if player_person:
                    player_person.person = person
                    player_person.platform = available_platform
                    player_person.save()

            except Exception as e:
                PersonPlayerId.objects.create(
                    person=person,
                    player_id=player_id,
                    platform=available_platform,
                )

        serializer = PersonGetSerializer(
            person, context={"lang": lang, "is_password_required": True}
        )

        admin_data = getadmincontact(
            serializer.data.get("flag_show"), lang, serializer.data.get("surname")
        )
        # if  and len(admin_data.get('admin_data',[])) > 0 :
        #     return Response(admin_data, status=status.HTTP_200_OK)
        admin_data["person"] = serializer.data
        # admin_data["person"]["is_show_old_contact"] = True
        admin_user_id = serializer.data.get("id")
        if admin_user_id:
            person = Person.objects.get(pk=admin_user_id, is_deleted=False)
            if person.is_admin or person.is_super_admin:
                surname = person.surname
                pending_users = Person.objects.filter(
                    flag_show=False, surname=surname, is_deleted=False
                ).exclude(id=surname.top_member)
                pendingdata_count = pending_users.count()
            else:
                pendingdata_count = 0
            response_data = {"pending-data": pendingdata_count}
            response_data.update(admin_data)
            return Response(response_data, status=status.HTTP_200_OK)


class AdditionalData(APIView):
    def get(self, request):
        additional_data_entry = AdsSetting.objects.values("ads_setting").first()
        additional_data = (
            additional_data_entry["ads_setting"] if additional_data_entry else {}
        )
        return Response({"additional_data": additional_data}, status=status.HTTP_200_OK)


class V3SurnameDetailView(APIView):
    authentication_classes = []

    def get(self, request):
        person_id = request.GET.get("person_id")
        lang = request.GET.get("lang", "en")
        try:
            person = Person.objects.get(id=person_id, is_deleted=False)
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


def append_to_log(filename, message):
    """Append a message to an existing log file, creating the file if it doesn't exist."""
    with open(filename, "a") as file:
        file.write(message + "\n")


class V3BannerDetailView(APIView):
    def get(self, request):
        today = datetime.now().date()
        Banner.objects.filter(
            expire_date__lt=today, is_active=True, is_deleted=False
        ).update(is_active=False)
        active_banner = Banner.objects.filter(
            is_active=True, expire_date__gte=today, is_deleted=False
        ).order_by("expire_date")
        expire_banner = Banner.objects.filter(
            is_active=False, expire_date__lt=today, is_deleted=False
        ).order_by("-expire_date")

        active_banner_data = BannerGETSerializer(active_banner, many=True).data
        expire_banner_data = BannerGETSerializer(expire_banner, many=True).data
        is_random_banner = RandomBanner.objects.values_list(
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
        person = get_object_or_404(Person, id=created_person).id
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

    def put(self, request):

        banner_id = request.data.get("banner_id")
        if not banner_id:
            return Response(
                {"message": "Please enter Banner Details"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        banner = get_object_or_404(Banner, id=banner_id)
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
            banner = get_object_or_404(Banner, pk=pk)
            if banner.is_deleted == False:
                banner.is_active = False
                banner.is_deleted = True
                banner.save()
                return Response(
                    {"message": f"Banner record ID {pk} deleted successfully."},
                    status=status.HTTP_204_NO_CONTENT,
                )
            else:
                return Response(
                    {"message": f"Banner record ID {pk} already deleted."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        except Exception as e:
            return Response(
                {
                    "message": f"Failed to delete the Banner record with ID {pk}: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RandomBannerView(APIView):
    def post(self, request):
        is_random_banner = False
        if "is_random_banner" in request.data:
            is_random_banner = request.data.get("is_random_banner").lower()
            if is_random_banner == "true":
                is_random_banner = True
            else:
                is_random_banner = False
        try:
            data = RandomBanner.objects.all().first()
            if data:
                data.is_random_banner = is_random_banner
                data.save()
                return Response(
                    {"message": "data Successfully updated"}, status=status.HTTP_200_OK
                )
            else:
                RandomBanner.objects.create(is_random_banner=is_random_banner)
                return Response(
                    {"message": "data Successfully created"},
                    status=status.HTTP_201_CREATED,
                )
        except Exception as error:
            return Response({"message": f"{error}"}, status=status.HTTP_400_BAD_REQUEST)


def capitalize_name(name):
    return name.capitalize()


class FirstCapitalize(APIView):
    def get(self, request):
        person = Person.objects.all()
        for i in person:
            i.first_name = capitalize_name(i.first_name)
            i.middle_name = capitalize_name(i.middle_name)
            i.save()
        return Response({"okay"})
