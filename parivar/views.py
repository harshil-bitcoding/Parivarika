from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from parivar.v3.views import capitalize_name, updated_log
from .models import *
from .serializers import *
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from django.db.models import Q
from logging import getLogger
from PIL import Image, ImageFile
from io import BytesIO

from django.conf import settings
from django.http import Http404

from django.db.models import Case, When, F, Q

from PIL import Image
from io import BytesIO

from PIL import Image
from django.core.files import File
import cv2
import os
import numpy as np
from django.contrib.auth import authenticate

from django.db import IntegrityError

import logging
from .signals import *

logger = logging.getLogger(__name__)


def index(request):
    return HttpResponse("Hello, world. This is the index page.")


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


class LoginAPI(APIView):

    def post(self, request):
        mobile_number = request.data.get("mobile_number")
        lang = request.data.get("lang", "en")

        if mobile_number is None or mobile_number == "":
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
        serializer = PersonGetSerializer(
            person, context={"lang": lang, "is_password_required": True}
        )
        admin_data = getadmincontact(
            serializer.data.get("flag_show"), lang, serializer.data.get("surname")
        )
        # if  and len(admin_data.get('admin_data',[])) > 0 :
        #     return Response(admin_data, status=status.HTTP_200_OK)
        admin_data["person"] = serializer.data
        admin_data["person"]["is_show_old_contact"] = True
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


class SurnameDetailView(APIView):
    authentication_classes = []

    def get(self, request):
        surnames = Surname.objects.all().order_by("fix_order")
        lang = request.GET.get("lang", "en")
        serializer = SurnameSerializer(surnames, many=True, context={"lang": lang})
        return Response(serializer.data, status=status.HTTP_200_OK)

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


class PersonBySurnameView(APIView):
    def post(self, request):
        surname = request.data.get("surname")
        lang = request.data.get("lang", "en")
        is_father_selection = request.data.get("is_father_selection", "").lower()

        if not surname:
            message = "અટક જરૂરી છે" if lang == "guj" else "Surname ID is required"
            return JsonResponse({"message": message, "data": []}, status=400)

        surname_data = Surname.objects.filter(id=int(surname)).first()
        if not surname_data:
            return JsonResponse({"data": []}, status=200)

        top_member = int(GetSurnameSerializer(surname_data).data.get("top_member", 0))
        person_filters = {"surname__id": int(surname), "flag_show": True}

        persons = Person.objects.filter(**person_filters).exclude(id=top_member)

        if is_father_selection == "true":
            persons = persons.order_by("first_name")
        else:
            persons = (
                persons.filter(mobile_number1__isnull=False)
                .exclude(mobile_number1="")
                .order_by("first_name")
            )

        if persons.exists():
            serializer = PersonGetSerializer(persons, many=True, context={"lang": lang})
            if serializer.data:
                data = sorted(
                    serializer.data,
                    key=lambda x: (x["first_name"], x["middle_name"], x["surname"]),
                )
                return JsonResponse({"data": data})

        return JsonResponse({"data": []}, status=200)


class BloodGroupDetailView(APIView):
    def get(self, request):
        bloodgroup = BloodGroup.objects.all()
        serializer = BloodGroupSerializer(bloodgroup, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PendingApproveDetailView(APIView):
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
                person = Person.objects.get(pk=admin_user_id, is_deleted=False)
            except Person.DoesNotExist:
                return Response(
                    {"message": "User not found"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            if not person.is_admin and not person.is_super_admin:
                return Response(
                    {"message": "User does not have admin access"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Get surname based on admin user (assuming relationship exists)
            surname = (
                person.surname
            )  # Modify this line based on your model relationships

            # Filter users by surname instead of top_member
            if person.is_super_admin == True:
                pending_users = Person.objects.filter(
                    flag_show=False, is_deleted=False
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
                    "child": PersonGetSerializer(
                        child_users, many=True, context={"lang": lang}
                    ).data,
                    "others": PersonGetSerializer(
                        other_users, many=True, context={"lang": lang}
                    ).data,
                }
            elif person.is_admin == True:

                pending_users = Person.objects.filter(
                    flag_show=False, surname=surname, is_deleted=False
                ).exclude(id=surname.top_member)
                if not pending_users.exists():
                    return Response(
                        {
                            "message": "No users with pending confirmation for this surname"
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
                child_users = pending_users.filter(child_flag=True).order_by(
                    "first_name"
                )
                other_users = pending_users.exclude(child_flag=True).order_by(
                    "first_name"
                )

                data = {
                    "child": PersonGetSerializer(
                        child_users, many=True, context={"lang": lang}
                    ).data,
                    "others": PersonGetSerializer(
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
                admin_person = Person.objects.get(pk=admin_user_id, is_deleted=False)
            except Person.DoesNotExist:
                logger.error(f"Person with ID {admin_user_id} not found")
                return Response(
                    {"message": f"Admin Person not found"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            if not (admin_person.is_admin or admin_person.is_super_admin):
                return Response(
                    {"message": "User does not have admin access"},
                    status=status.HTTP_200_OK,
                )
            user_id = request.data.get("user_id")
            if not user_id:
                return Response(
                    {"message": "Missing User in request data"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            try:
                person = Person.objects.get(pk=user_id, is_deleted=False)
            except Person.DoesNotExist:
                logger.error(f"Person with ID {user_id} not found")
                return Response(
                    {"message": f"Person not found"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            if person.flag_show:
                return Response(
                    {"message": "User Already Approved"},
                    status=status.HTTP_202_ACCEPTED,
                )
            flag_show = request.data.get("flag_show", person.flag_show)
            person.flag_show = flag_show
            person.save()
            serializer = PersonGetSerializer(person)
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
                return Response(
                    {"message": f"Admin Person not found"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            if not (admin_person.is_admin or admin_person.is_super_admin):
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
            user_id = request.data.get("user_id")
            if not user_id or user_id is None or user_id == "":
                return Response(
                    {"message": "Missing User in request data"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            try:
                person = Person.objects.get(pk=user_id, is_deleted=False)
            except Person.DoesNotExist:
                return Response(
                    {"message": f"Person not found"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
                    children = ParentChildRelation.objects.filter(
                        parent_id=user_id, is_deleted=False
                    )
                    for child in children:
                        child.parent_id = top_member_ids[0]
                        child.save()
                try:
                    child_data = ParentChildRelation.objects.get(
                        child_id=user_id, is_deleted=False
                    )
                    child_data.is_deleted = True
                    child_data.save()
                except:
                    pass
            except Surname.DoesNotExist:
                return Response(
                    {"message": f"Surname not exist"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            return Response(
                {"message": f"Failed to delete the for this record"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PersonDetailView(APIView):
    def get(self, request, pk):
        try:
            lang = request.GET.get("lang", "en")
            person = Person.objects.get(id=pk, is_deleted=False)
            if person:
                person = PersonGetSerializer(
                    person, context={"lang": lang, "is_password_required": True}
                ).data
                person["child"] = []
                person["parent"] = {}
                person["brother"] = []
                child_data = ParentChildRelation.objects.filter(
                    parent=int(person["id"]), is_deleted=False
                ).order_by("child__date_of_birth")
                if child_data.exists():
                    child_data = GetParentChildRelationSerializer(
                        child_data, many=True, context={"lang": lang}
                    ).data
                    for child in child_data:
                        person["child"].append(child.get("child"))
                person_id = Person.objects.get(id=pk, is_deleted=False)
                child_relation = Surname.objects.get(id=person_id.surname.id)
                parent_data = (
                    ParentChildRelation.objects.filter(child=int(person["id"]))
                    .exclude(parent=child_relation.top_member)
                    .first()
                )
                if parent_data:
                    parent_data = GetParentChildRelationSerializer(
                        parent_data, context={"lang": lang}
                    ).data
                    person["parent"] = parent_data.get("parent")
                    brother_data = ParentChildRelation.objects.filter(
                        parent=int(parent_data.get("parent").get("id", 0)),
                        is_deleted=False,
                    ).order_by("child__date_of_birth")
                    if brother_data.exists():
                        brother_data = GetParentChildRelationSerializer(
                            brother_data, many=True, context={"lang": lang}
                        ).data
                        for brother in brother_data:
                            if int(person["id"]) != int(brother["child"]["id"]):
                                person["brother"].append(brother.get("child"))
                return Response(person, status=status.HTTP_200_OK)
        except Person.DoesNotExist:
            if lang == "guj":
                return Response(
                    {"error": "વ્યક્તિ મળી રહી નથી"}, status=status.HTTP_404_NOT_FOUND
                )
            else:
                return Response(
                    {"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND
                )

    def post(self, request):
        surname = request.data.get("surname", 0)
        persons_surname_wise = Surname.objects.filter(Q(id=int(surname))).first()
        persons_surname_wise_data = None
        father = request.data.get("father", 0)
        top_member = 0
        if persons_surname_wise:
            persons_surname_wise_data = SurnameSerializer(persons_surname_wise).data
            top_member = int(persons_surname_wise_data.get("top_member", 0))
            if father == 0:
                father = top_member
        children = request.data.get("child", [])
        first_name = capitalize_name(request.data.get("first_name"))
        middle_name = capitalize_name(request.data.get("middle_name"))
        address = request.data.get("address")
        out_of_address = request.data.get("out_of_address")
        lang = request.data.get("lang", "en")
        date_of_birth = request.data.get("date_of_birth")
        blood_group = request.data.get("blood_group", 1)
        # city = request.data.get("city",52)
        # state = request.data.get("state",3)
        out_of_country = request.data.get("out_of_country", 1)
        if int(out_of_country) == 0:
            out_of_country = 1
        mobile_number1 = request.data.get("mobile_number1")
        mobile_number2 = request.data.get("mobile_number2")
        status_name = request.data.get("status")
        is_admin = request.data.get("is_admin")
        is_registered_directly = request.data.get("is_registered_directly")
        out_of_mobile = request.data.get("out_of_mobile", "")
        is_same_as_father_address = request.data.get("is_same_as_father_address", False)
        is_same_as_son_address = request.data.get("is_same_as_son_address", False)
        platform = request.data.get("platform")
        person_data = {
            "first_name": first_name,
            "middle_name": middle_name,
            "address": address,
            "out_of_address": out_of_address,
            "date_of_birth": date_of_birth,
            "blood_group": blood_group,
            "city": 52,
            "state": 3,
            "out_of_country": out_of_country,
            "mobile_number1": mobile_number1,
            "mobile_number2": mobile_number2,
            "status": status_name,
            "surname": surname,
            "is_admin": is_admin,
            "is_registered_directly": is_registered_directly,
            "out_of_mobile": out_of_mobile,
            "is_same_as_father_address": is_same_as_father_address,
            "is_same_as_son_address": is_same_as_son_address,
            "platform": platform,
        }
        serializer = PersonSerializer(data=person_data)

        if serializer.is_valid():
            if len(children) > 0:
                children_exist = ParentChildRelation.objects.filter(child__in=children)
                if children_exist.exclude(parent=top_member).exists():
                    return JsonResponse(
                        {"message": "Children already exist"}, status=400
                    )
                children_exist.filter(parent=top_member).delete()
            persons = serializer.save()
            persons.save()
            try:
                if not first_name:
                    if lang == "guj":
                        raise ValueError("first_name is required")
                    else:
                        raise ValueError("નામ જરૂરી છે")
            except IntegrityError as e:
                print(f"IntegrityError encountered: {e}")
            parent_serializer = ParentChildRelationSerializer(
                data={"parent": father, "child": persons.id, "created_user": persons.id}
            )
            if parent_serializer.is_valid():
                parent_serializer.save()
            for child in children:
                child_serializer = ParentChildRelationSerializer(
                    data={
                        "child": child,
                        "parent": persons.id,
                        "created_user": persons.id,
                    }
                )
                if child_serializer.is_valid():
                    child_serializer.save()
            if lang != "en":
                person_translate_data = {
                    "first_name": first_name,
                    "person_id": persons.id,
                    "middle_name": middle_name,
                    "address": address,
                    "out_of_address": out_of_address,
                    "language": lang,
                }
                person_translate_serializer = TranslatePersonSerializer(
                    data=person_translate_data
                )
                if person_translate_serializer.is_valid():
                    person_translate_serializer.save()
            surname_field = "guj_name" if lang == "guj" else "name"
            per_data = PersonGetSerializer(persons, context={"lang": lang}).data
            admin_data = getadmincontact(
                persons.flag_show, lang, persons_surname_wise_data.get(surname_field)
            )
            # if admin_data and len(admin_data.get('admin_data',[])) > 0 :
            admin_data["person"] = per_data
            return Response(admin_data, status=status.HTTP_201_CREATED)

            # return Response({"person" : per_data}, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        person = get_object_or_404(Person, pk=pk)
        if not person:
            if lang == "guj":
                return JsonResponse(
                    {"message": "વ્યક્તિ મળી રહીયો નથી"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                return JsonResponse(
                    {"message": "Person not found"}, status=status.HTTP_400_BAD_REQUEST
                )
        surname = request.data.get("surname", 0)
        persons_surname_wise = Surname.objects.filter(Q(id=int(surname))).first()
        father = request.data.get("father", 0)
        top_member = 0
        if persons_surname_wise:
            top_member = int(
                GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0)
            )
            if father == 0:
                father = top_member
        children = request.data.get("child", [])
        first_name = capitalize_name(request.data.get("first_name"))
        middle_name = capitalize_name(request.data.get("middle_name"))
        address = request.data.get("address")
        out_of_address = request.data.get("out_of_address")
        lang = request.data.get("lang", "en")
        date_of_birth = request.data.get("date_of_birth")
        blood_group = request.data.get("blood_group", 1)
        # city = request.data.get("city")
        # state = request.data.get("state")
        out_of_country = request.data.get("out_of_country", 1)
        if int(out_of_country) == 0:
            out_of_country = 1
        mobile_number1 = request.data.get("mobile_number1")
        mobile_number2 = request.data.get("mobile_number2")
        if "out_of_mobile" in request.data:
            out_of_mobile = request.data.get("out_of_mobile")
        else:
            out_of_mobile = person.out_of_mobile
        if "is_same_as_father_address" in request.data:
            is_same_as_father_address = request.data.get("is_same_as_father_address")
        else:
            is_same_as_father_address = person.is_same_as_father_address
        if "is_same_as_son_address" in request.data:
            is_same_as_son_address = request.data.get("is_same_as_son_address")
        else:
            is_same_as_son_address = person.is_same_as_son_address
        person_data = {
            "first_name": first_name if lang == "en" else person.first_name,
            "middle_name": middle_name if lang == "en" else person.middle_name,
            "address": address if lang == "en" else person.address,
            "out_of_address": out_of_address,
            "date_of_birth": date_of_birth,
            "blood_group": blood_group,
            "city": 52,
            "state": 3,
            "out_of_mobile": out_of_mobile,
            "out_of_country": out_of_country,
            "mobile_number1": mobile_number1,
            "mobile_number2": mobile_number2,
            "surname": surname,
            "is_same_as_father_address": is_same_as_father_address,
            "is_same_as_son_address": is_same_as_son_address,
        }
        # person_data = {
        #     'first_name' : person.first_name if lang == 'en' else first_name,
        #     'middle_name' : person.middle_name if lang == 'en' else middle_name,
        #     'address' : person.address if lang == 'en' else address,
        #     'out_of_address': out_of_address,
        #     'date_of_birth': date_of_birth,
        #     'blood_group': blood_group,
        #     'city': city,
        #     'state': state,
        #     'out_of_country': out_of_country,
        #     'mobile_number1': mobile_number1,
        #     'mobile_number2': mobile_number2,
        #     'surname': surname
        # }
        serializer = PersonSerializer(
            person, data=person_data, context={"person_id": person.id}
        )
        if serializer.is_valid():
            if len(children) > 0:
                children_exist = ParentChildRelation.objects.filter(child__in=children)
                if (
                    children_exist.exclude(parent=top_member)
                    .exclude(parent=person.id)
                    .exists()
                ):
                    return JsonResponse(
                        {"message": "Children already exist"}, status=400
                    )
            persons = serializer.save()

            father_data = ParentChildRelation.objects.filter(child=persons.id)
            data = {"parent": father, "child": persons.id, "created_user": persons.id}
            father_data_serializer = None
            if father_data.exists():
                father_data = father_data.first()
                father_data_serializer = ParentChildRelationSerializer(
                    father_data, data=data
                )
            else:
                father_data_serializer = ParentChildRelationSerializer(data=data)
            if father_data_serializer.is_valid():
                father_data_serializer.save()

            for child in children:
                child_data = ParentChildRelation.objects.filter(child=child)
                data = {
                    "child": child,
                    "parent": persons.id,
                    "created_user": persons.id,
                }
                child_data_serializer = None
                if child_data.exists():
                    child_data = child_data.first()
                    child_data_serializer = ParentChildRelationSerializer(
                        child_data, data=data
                    )
                else:
                    child_data_serializer = ParentChildRelationSerializer(data=data)
                if child_data_serializer.is_valid():
                    child_data_serializer.save()

            if len(children) > 0:
                remove_child_person = ParentChildRelation.objects.filter(
                    parent=persons.id
                ).exclude(child__in=children)
                if remove_child_person.exists():
                    for child in remove_child_person:
                        child.parent_id = int(top_member)
                        child.save()

            if lang != "en":
                lang_data = TranslatePerson.objects.filter(
                    person_id=persons.id, is_deleted=False
                ).filter(language=lang)
                if lang_data.exists():
                    lang_data = lang_data.first()
                    person_translate_data = {
                        "first_name": first_name,
                        "middle_name": middle_name,
                        "address": address,
                        "out_of_address": out_of_address,
                        "language": lang,
                    }
                    person_translate_serializer = TranslatePersonSerializer(
                        lang_data, data=person_translate_data
                    )
                    if person_translate_serializer.is_valid():
                        person_translate_serializer.save()
            return Response(
                {
                    "person": PersonGetSerializer(
                        persons, context={"lang": lang, "is_password_required": True}
                    ).data
                },
                status=status.HTTP_200_OK,
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        lang = request.data.get("lang", "en")
        person = get_object_or_404(Person, pk=pk)
        try:
            person_child_data = Surname.objects.get(id=person.surname.id)
            topmaember_id = person_child_data.top_member
            if topmaember_id == pk:
                if lang == "guj":
                    return Response(
                        {"message": "આ સભ્ય માટે વિગત કાઢી નાખવાની મંજૂરી નથી."},
                        status=status.HTTP_204_NO_CONTENT,
                    )
                else:
                    return Response(
                        {"message": "Delete profile is not allowed for this person."},
                        status=status.HTTP_204_NO_CONTENT,
                    )
            topmaember = Person.objects.get(id=topmaember_id, is_deleted=False)
            if person_child_data:
                relation_child_data = ParentChildRelation.objects.filter(
                    parent_id=person.id
                )

                for relation in relation_child_data:
                    relation.parent = topmaember
                    relation.created_user = topmaember
                    child_data = Person.objects.filter(id=relation.child.id)
                    for data in child_data:
                        data.middle_name = topmaember.first_name
                        data.save()
                    translate_data_1111 = TranslatePerson.objects.filter(
                        person_id=relation.child.id, is_deleted=False
                    )
                    for i in translate_data_1111:
                        i.middle_name = topmaember.surname.guj_name
                        i.save()

                    # relation.save()
                child_relation_data = ParentChildRelation.objects.get(
                    child_id=person.id, is_deleted=False
                )
                child_relation_data.is_deleted = True
                child_relation_data.save()
                relation_create = ParentChildRelation.objects.filter(
                    created_user=person
                )
                for i in relation_create:
                    i.created_user = topmaember
                    # i.save()
                translate_data = TranslatePerson.objects.filter(
                    person_id=person, is_deleted=False
                )
                for i in translate_data:
                    i.is_deleted = True
                    i.save()
                person.flag_show = False
                person.is_deleted = True
                person.save()
            if lang == "guj":
                return Response(
                    {"message": "સભ્યની વિગત સફળતાપૂર્વક કાઢી નાખ્યો."},
                    status=status.HTTP_204_NO_CONTENT,
                )
            else:
                return Response(
                    {"message": "Delete profile in record in review."},
                    status=status.HTTP_204_NO_CONTENT,
                )
        except Exception as e:
            if lang == "guj":
                return Response(
                    {"message": f"સભ્યની વિગત કાઢી નાખવામાં નિષ્ફળ રહ્યા: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": f"Failed to delete the person record: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )


class AdminPersonDetailView(APIView):
    def get(self, request, pk, admin_user_id):
        lang = request.GET.get("lang", "en")
        error_messages = {
            "admin_missing": {
                "en": "Missing Admin User in request data",
                "guj": "એડમીન સભ્ય ડેટામાં મળી રહીયો નથી",
            },
            "person_not_found": {
                "en": "Admin Person not found",
                "guj": "એડમિન સભ્ય મળતો નથી",
            },
            "no_admin_access": {
                "en": "User does not have admin access",
                "guj": "વપરાશકર્તા સભ્ય પાસે એડમિન એક્સેસ નથી",
            },
            "person_data_not_found": {
                "en": "Person not found",
                "guj": "વ્યક્તિ મળી રહીયો નથી",
            },
        }

        if not admin_user_id:
            return Response(
                {"message": error_messages["admin_missing"][lang]},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            admin_person = Person.objects.get(pk=admin_user_id, is_deleted=False)
        except Person.DoesNotExist:
            logger.error(f"Person with ID {admin_user_id} not found")
            return Response(
                {"message": error_messages["person_not_found"][lang]},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not (admin_person.is_admin or admin_person.is_super_admin):
            return Response(
                {"message": error_messages["no_admin_access"][lang]},
                status=status.HTTP_200_OK,
            )

        try:
            person = Person.objects.get(id=pk, is_deleted=False)
            serialized_person = AdminPersonGetSerializer(
                person, context={"lang": lang}
            ).data
            serialized_person["child"] = []
            serialized_person["parent"] = {}
            serialized_person["brother"] = []

            # Fetch and add child data
            topmemeber = Surname.objects.get(id=person.surname.id)
            child_relations = ParentChildRelation.objects.filter(
                parent=person.id
            ).exclude(parent=topmemeber.top_member)
            if child_relations.exists():
                serialized_children = GetParentChildRelationSerializer(
                    child_relations, many=True, context={"lang": lang}
                ).data
                serialized_person["child"] = [
                    child.get("child") for child in serialized_children
                ]

            parent_relation = (
                ParentChildRelation.objects.filter(child=person.id)
                .exclude(parent=topmemeber.top_member)
                .first()
            )
            if parent_relation:
                serialized_parent = GetParentChildRelationSerializer(
                    parent_relation, context={"lang": lang}
                ).data
                serialized_person["parent"] = serialized_parent.get("parent")

                if serialized_person["parent"]:
                    parent_id = serialized_person["parent"].get("id")
                    brother_relations = ParentChildRelation.objects.filter(
                        parent=parent_id, parent__flag_show=True
                    ).exclude(parent=topmemeber.top_member)
                    serialized_brothers = GetParentChildRelationSerializer(
                        brother_relations, many=True, context={"lang": lang}
                    ).data
                    serialized_person["brother"] = [
                        brother.get("child")
                        for brother in serialized_brothers
                        if brother.get("child").get("id") != person.id
                    ]

            return Response(serialized_person, status=status.HTTP_200_OK)

        except Person.DoesNotExist:
            return Response(
                {"error": error_messages["person_data_not_found"][lang]},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        admin_user_id = request.data.get("admin_user_id")
        lang = request.data.get("lang")
        error_messages = {
            "admin_missing": {
                "en": "Missing Admin User in request data",
                "guj": "એડમીન સભ્ય ડેટામાં મળી રહીયો નથી",
            },
            "person_not_found": {
                "en": "Admin Person not found",
                "guj": "એડમિન સભ્ય મળતો નથી",
            },
            "no_admin_access": {
                "en": "User does not have admin access",
                "guj": "વપરાશકર્તા સભ્ય પાસે એડમિન એક્સેસ નથી",
            },
        }
        if not admin_user_id:
            if lang == "guj":
                return Response(
                    {"message": error_messages["admin_missing"][lang]},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        try:
            admin_person = Person.objects.get(pk=admin_user_id, is_deleted=False)
        except Person.DoesNotExist:
            return Response(
                {"message": error_messages["person_not_found"][lang]},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if not (admin_person.is_admin or admin_person.is_super_admin):
            return Response(
                {"message": error_messages["no_admin_access"][lang]},
                status=status.HTTP_200_OK,
            )
        surname = request.data.get("surname", 0)
        persons_surname_wise = Surname.objects.filter(Q(id=int(surname))).first()
        father = request.data.get("father", 0)
        top_member = 0
        if persons_surname_wise:
            top_member = int(
                GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0)
            )
            if father == 0:
                father = top_member
        children = request.data.get("child", [])
        if len(children) > 0:
            children_exist = ParentChildRelation.objects.filter(child__in=children)
            if children_exist.exclude(parent=top_member).exists():
                return JsonResponse({"message": "Children already exist"}, status=400)
            children_exist.filter(parent=top_member).delete()
        first_name = request.data.get("first_name")
        middle_name = request.data.get("middle_name")
        address = request.data.get("address")
        out_of_country = request.data.get("out_of_country", 1)
        if int(out_of_country) == 0:
            out_of_country = 1
        out_of_address = request.data.get("out_of_address")
        guj_first_name = request.data.get("guj_first_name")
        guj_middle_name = request.data.get("guj_middle_name")
        guj_address = request.data.get("guj_address")
        guj_out_of_address = request.data.get("guj_out_of_address")
        platform = request.data.get("platform")
        if lang is not None and lang != "en":
            if guj_first_name is None or guj_first_name == "":
                return JsonResponse({"message": "First Name is required"}, status=400)
            # if guj_middle_name is None or guj_middle_name  == "" :
            #     return JsonResponse({'message': 'Middle Name is required'}, status=400)
            # if guj_address is None or guj_address  == "" :
            #     return JsonResponse({'message': 'Address is required'}, status=400)
            # if (
            #     first_name is None
            #     or first_name == ""
            #     and guj_first_name is not None
            #     and guj_first_name != ""
            # ):
            #     first_name = guj_first_name
            # if (
            #     (middle_name is None or middle_name == "")
            #     and guj_middle_name is not None
            #     and guj_middle_name != ""
            # ):
            #     middle_name = guj_middle_name
            # if (
            #     (address is None or address == "")
            #     and guj_address is not None
            #     and guj_address != ""
            # ):
            #     address = guj_address
            # if (
            #     (out_of_address is None or out_of_address == "")
            #     and guj_out_of_address is not None
            #     and guj_out_of_address != ""
            # ):
            #     out_of_address = guj_out_of_address
        date_of_birth = request.data.get("date_of_birth")
        blood_group = request.data.get("blood_group")
        # city = request.data.get("city")
        # state = request.data.get("state")
        mobile_number1 = request.data.get("mobile_number1")
        mobile_number2 = request.data.get("mobile_number2")
        status_name = request.data.get("status")
        is_admin = request.data.get("is_admin")
        is_registered_directly = request.data.get("is_registered_directly")
        person_data = {
            "first_name": capitalize_name(first_name),
            "middle_name": capitalize_name(middle_name),
            "address": address,
            "out_of_address": out_of_address,
            "date_of_birth": date_of_birth,
            "blood_group": blood_group,
            "out_of_country": out_of_country,
            "city": 52,
            "state": 3,
            "flag_show": True,
            "mobile_number1": mobile_number1,
            "mobile_number2": mobile_number2,
            "status": status_name,
            "surname": surname,
            "is_admin": is_admin,
            "platform": platform,
            "is_registered_directly": is_registered_directly,
        }
        serializer = PersonSerializer(data=person_data)
        if serializer.is_valid():
            persons = serializer.save()
            parent_serializer = ParentChildRelationSerializer(
                data={"parent": father, "child": persons.id, "created_user": persons.id}
            )
            if parent_serializer.is_valid():
                parent_serializer.save()
            for child in children:
                child_serializer = ParentChildRelationSerializer(
                    data={
                        "child": child,
                        "parent": persons.id,
                        "created_user": persons.id,
                    }
                )
                if child_serializer.is_valid():
                    child_serializer.save()
            person_translate_data = {
                "first_name": guj_first_name,
                "person_id": persons.id,
                "middle_name": guj_middle_name,
                "out_of_address": guj_out_of_address,
                "middle_name": guj_middle_name,
                "address": guj_address,
                "language": "guj",
            }
            person_translate_serializer = TranslatePersonSerializer(
                data=person_translate_data
            )
            if person_translate_serializer.is_valid():
                person_translate_serializer.save()

            """ Create a Person Profile Update a  log"""

            updated_history = f" This Person is Created by {admin_person.first_name} {admin_person.surname}"
            updated_log(persons.id, updated_history, admin_person.id)

            return Response(
                {"person": AdminPersonGetSerializer(persons).data},
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        admin_user_id = request.data.get("admin_user_id")
        lang = request.data.get("lang", "en")
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
            if lang == "guj":
                return Response(
                    {"message": f"એડમિન વ્યક્તિ મળી રહીયો નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": f"Admin Person not found"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        if not (admin_person.is_admin or admin_person.is_super_admin):
            if lang == "guj":
                return Response(
                    {"message": "તમારી પાસે એડમિન સભ્ય બનાવવાની પરવાનગી નથી"},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"message": "User does not have admin access"},
                    status=status.HTTP_200_OK,
                )
        user_id = request.data.get("user_id")
        if not user_id:
            if lang == "guj":
                return Response(
                    {"message": "વિનંતી ડેટામાં વપરાશકર્તા નો સમાવેશ થયેલ નથી"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            else:
                return Response(
                    {"message": "Missing User in request data"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        person = get_object_or_404(Person, pk=user_id)
        try:
            if not person:
                if lang == "guj":
                    return JsonResponse(
                        {"message": "વ્યક્તિ મળી રહીયો નથી"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                else:
                    return JsonResponse(
                        {"message": "Person not found"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            surname = person.surname.id
            persons_surname_wise = Surname.objects.filter(Q(id=int(surname))).first()
            father = request.data.get("father", 0)
            top_member = 0
            if persons_surname_wise:
                top_member = int(
                    GetSurnameSerializer(persons_surname_wise).data.get("top_member", 0)
                )
                if father == 0:
                    father = top_member
            children = request.data.get("child", [])

            if "first_name" in request.data:
                person.first_name = capitalize_name(request.data.get("first_name"))

            if "middle_name" in request.data:
                person.middle_name = capitalize_name(request.data.get("middle_name"))

            if "address" in request.data:
                person.address = request.data.get("address")

            if "out_of_address" in request.data:
                person.out_of_address = request.data.get("out_of_address")

            if "date_of_birth" in request.data:
                person.date_of_birth = request.data.get("date_of_birth")

            if "blood_group" in request.data:
                person.blood_group = request.data.get("blood_group")

            if "city" in request.data:
                city = City.objects.get(id=52)
                person.city = city

            if "state" in request.data:
                state = State.objects.get(id=3)
                person.state = state

            if "out_of_country" in request.data:
                if request.data.get("out_of_country") == 0:
                    person.out_of_country = person.out_of_country
                else:
                    country = Country.objects.get(id=request.data.get("out_of_country"))
                    person.out_of_country = country

            if "guj_first_name" in request.data:
                guj_first_name = request.data.get("guj_first_name")

            if "guj_middle_name" in request.data:
                guj_middle_name = request.data.get("guj_middle_name")

            if "guj_address" in request.data:
                guj_address = request.data.get("guj_address")

            if "guj_out_of_address" in request.data:
                guj_out_of_address = request.data.get("guj_out_of_address")

            if "flag_show" in request.data:
                person.flag_show = request.data.get("flag_show")

            if "mobile_number1" in request.data:
                mobile_number1 = request.data.get("mobile_number1")
                if mobile_number1 not in [None, "", "null"]:
                    if len(mobile_number1) != 10 or not mobile_number1.isdigit():
                        return Response(
                            {"error": "Mobile Number1 must be exactly 10 digits long"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    existing_person = Person.objects.filter(
                        Q(mobile_number1=mobile_number1)
                        | Q(mobile_number2=mobile_number1),
                        is_deleted=False,
                    ).exclude(id=person.id)
                    if existing_person.exists():
                        return Response(
                            {
                                "error": "Mobile Number1 already registered please enter a new mobile number"
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    person.mobile_number1 = mobile_number1

            if "mobile_number2" in request.data:
                mobile_number2 = request.data.get("mobile_number2")
                if mobile_number2 not in [None, "", "null"]:
                    if len(mobile_number2) != 10 or not mobile_number2.isdigit():
                        return Response(
                            {"error": "Mobile Number1 must be exactly 10 digits long"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    existing_person = Person.objects.filter(
                        Q(mobile_number1=mobile_number1)
                        | Q(mobile_number2=mobile_number1),
                        is_deleted=False,
                    ).exclude(id=person.id)
                    if existing_person.exists():
                        return Response(
                            {
                                "error": "Mobile Number2 already registered please enter a new mobile number"
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    person.mobile_number2 = mobile_number2

            if "status" in request.data:
                person.status = request.data.get("status")
            if "surname" in request.data:
                person.surname = request.data.get("surname")
            if "is_admin" in request.data:
                person.is_admin = request.data.get("is_admin")
            if "is_registered_directly" in request.data:
                person.is_registered_directly = request.data.get(
                    "is_registered_directly"
                )
            if "out_of_mobile" in request.data:
                person.out_of_mobile = request.data.get("out_of_mobile")
            if "is_same_as_father_address" in request.data:
                person.is_same_as_father_address = request.data.get(
                    "is_same_as_father_address"
                )
            if "is_same_as_son_address" in request.data:
                person.is_same_as_son_address = request.data.get(
                    "is_same_as_son_address"
                )
            if len(children) > 0:
                children_exist = ParentChildRelation.objects.filter(child__in=children)
                if (
                    children_exist.exclude(parent=top_member)
                    .exclude(parent=person.id)
                    .exists()
                ):
                    if lang == "guj":
                        return JsonResponse(
                            {"message": "આ બાળક પહેલેથી જ બીજા સભ્ય સાથે જોડાયેલો છે"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    else:
                        return JsonResponse(
                            {
                                "message": "This child is already linked to another member"
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
            person.save()
            father_data = ParentChildRelation.objects.filter(child=person.id)
            if father_data.exists():
                father_data.update(child=person.id, parent=father)
            else:
                child_data = person
                parent = Person.objects.get(id=int(father), is_deleted=False)
                admin_user = Person.objects.get(id=int(admin_user_id), is_deleted=False)
                ParentChildRelation.objects.create(
                    child=child_data, parent=parent, created_user=admin_user
                )
            for child in children:
                child_data = ParentChildRelation.objects.filter(child=child)
                if child_data.exists():
                    child_data.update(parent=person.id, child=child)
                else:
                    child_data = Person.objects.get(id=int(child), is_deleted=False)
                    parent = person
                    admin_user = Person.objects.get(
                        id=int(admin_user_id), is_deleted=False
                    )
                    ParentChildRelation.objects.create(
                        child=child_data, parent=parent, created_user=admin_user
                    )
            if len(children) > 0:
                remove_child_person = ParentChildRelation.objects.filter(
                    parent=person.id
                ).exclude(child__in=children)
                if remove_child_person.exists():
                    for child in remove_child_person:
                        child.update(parent_id=int(top_member))
            lang_data = TranslatePerson.objects.filter(
                person_id=person.id, is_deleted=False
            ).filter(language="guj")
            if lang_data.exists():
                lang_data = lang_data.update(
                    person_id=person.id,
                    first_name=guj_first_name,
                    middle_name=guj_middle_name,
                    address=guj_address,
                    out_of_address=guj_out_of_address,
                )
            else:
                lang_data = TranslatePerson.objects.create(
                    person_id=person,
                    first_name=guj_first_name,
                    middle_name=guj_middle_name,
                    address=guj_address,
                    out_of_address=guj_out_of_address,
                    language="guj",
                )

            """ Create a Person Profile Update a  log"""

            updated_history = f" This Person Profile is Updated by {admin_person.first_name} {admin_person.surname}"
            updated_log(person.id, updated_history, admin_person.id)

            if lang == "guj":
                return Response(
                    {"message": "સભ્ય-ડેટા સફળતાપૂર્વક અપડેટ કર્યા"},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"message": "Successfully updated member-data"},
                    status=status.HTTP_200_OK,
                )
        except Exception as e:
            if lang == "guj":
                return Response({"message": "સભ્ય પહેલેથી જ મંજૂર છે"})
            else:
                return Response({"message": f"Member is Already Approve  ,{e}"})

    def delete(self, request, pk, admin_user_id=None):
        try:
            person = get_object_or_404(Person, pk=pk)
            person_name = person.first_name
            lang = request.data.get("lang", "en")
            admin_user_id = admin_user_id
            error_messages = {
                "admin_missing": {
                    "en": "Missing Admin User in request data",
                    "guj": "એડમીન સભ્ય ડેટામાં મળી રહીયો નથી",
                },
                "person_not_found": {
                    "en": "Admin Person not found",
                    "guj": "એડમિન સભ્ય મળતો નથી",
                },
                "no_admin_access": {
                    "en": "you have not admin access",
                    "guj": "વપરાશકર્તા સભ્ય પાસે એડમિન એક્સેસ નથી",
                },
            }
            if not admin_user_id:
                if lang == "guj":
                    return Response(
                        {"message": error_messages["admin_missing"][lang]},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            try:
                admin_person = Person.objects.get(pk=admin_user_id, is_deleted=False)
            except Person.DoesNotExist:
                return Response(
                    {"message": error_messages["person_not_found"][lang]},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            if not (admin_person.is_admin or admin_person.is_super_admin):
                return Response(
                    {"message": error_messages["no_admin_access"][lang]},
                    status=status.HTTP_200_OK,
                )
            person_child_data = Surname.objects.get(id=person.surname.id)
            topmaember_id = person_child_data.top_member
            topmaember = Person.objects.get(id=topmaember_id, is_deleted=False)
            if admin_user_id != pk:
                if person_child_data:
                    relation_child_data = ParentChildRelation.objects.filter(
                        parent_id=person.id
                    )
                    for relation in relation_child_data:
                        relation.parent = topmaember
                        relation.created_user = topmaember
                        relation.save()
                        child_data = Person.objects.filter(id=relation.child.id)
                        for data in child_data:
                            data.middle_name = topmaember.first_name
                            data.save()

                    child_relation_data = ParentChildRelation.objects.get(
                        child_id=person.id
                    )
                    child_relation_data.is_deleted = True
                    child_relation_data.save()
                    person_name = person.first_name
                    person.flag_show = False
                    person.is_deleted = True
                    person.save()
                return Response(
                    {"message": f"Person record {person_name} Deleted successfully."},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"message": f"Person record {person_name} not Deleted."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        except Exception as e:
            return Response(
                {
                    "message": "An error occurred while Delete the person record. Please try again later."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class AdminAccess(APIView):
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
            serializer = PersonSerializer(admin_access, many=True)
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


class CityDetailView(APIView):
    def get(self, request, state_id):
        lang = request.GET.get("lang", "en")
        try:
            state = State.objects.prefetch_related("state").get(id=state_id)
        except State.DoesNotExist:
            return Response(
                {"error": "State not found"}, status=status.HTTP_404_NOT_FOUND
            )
        if lang == "guj":
            state = state.state.all().order_by("guj_name")
        else:
            state = state.state.all().order_by("name")
        serializer = CitySerializer(state, many=True, context={"lang": lang})
        city_list = serializer.data
        for index, instance in enumerate(city_list):
            if instance["id"] == 52:
                instance["sort_no"] = 0
            elif instance["id"] == 796:
                instance["sort_no"] = 1
            elif instance["id"] == 2:
                instance["sort_no"] = 2
            else:
                instance["sort_no"] = 3
        city_list = sorted(city_list, key=lambda x: (x["sort_no"], x["name"]))
        return Response(city_list, status=status.HTTP_200_OK)


class StateDetailView(APIView):
    def get(self, request):
        lang = request.GET.get("lang", "en")
        if lang == "guj":
            state = State.objects.all().order_by("guj_name")
        else:
            state = State.objects.all().order_by("name")
        serializer = StateSerializer(state, many=True, context={"lang": lang})
        # Update the index of the saved instances
        state_list = serializer.data
        for index, instance in enumerate(state_list):
            if instance["id"] == 3:
                instance["sort_no"] = 0
            else:
                instance["sort_no"] = 1
        state_list = sorted(state_list, key=lambda x: (x["sort_no"], x["name"]))
        return Response(state_list, status=status.HTTP_200_OK)


class CountryDetailView(APIView):
    def get(self, request):
        country = Country.objects.all()
        lang = request.GET.get("lang", "en")
        serializer = CountrySerializer(country, many=True, context={"lang": lang})
        country_list = serializer.data

        sort_order = {1: 0, 55: 1, 3: 2, 95: 3, 19: 4, 12: 5, 38: 6}

        for instance in country_list:
            instance["sort_no"] = sort_order.get(instance["id"], 7)

        sorted_data = sorted(country_list, key=lambda x: (x["sort_no"], x["name"]))
        return Response(sorted_data, status=status.HTTP_200_OK)


class BannerDetailView(APIView):
    def get(self, request):
        active_notifications = Banner.objects.filter(is_active=True)
        serializer = BannerSerializer(active_notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        images = request.FILES.getlist("banner_images")
        for banner in images:
            serializer = BannerSerializer(
                data={
                    "title": request.data.get("title"),
                    "sub_title": request.data.get("sub_title"),
                    "image_url": banner,
                    "redirect_url": request.data.get("redirect_url"),
                }
            )
            if serializer.is_valid():
                serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, pk):
        try:
            banner = get_object_or_404(Banner, pk=pk)
            banner.delete()
            return Response(
                {"message": f"Banner record ID {pk} deleted successfully."},
                status=status.HTTP_204_NO_CONTENT,
            )
        except Http404:
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


class ParentChildRelationDetailView(APIView):
    def post(self, request):
        serializer = ParentChildRelationSerializer(data=request.data)
        if serializer.is_valid():
            parent_id = serializer.validated_data.get("parent_id")
            child_id = serializer.validated_data.get("child_id")
            try:
                existing_relation = ParentChildRelation.objects.get(child_id=child_id)
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
                Person.objects.filter(surname__id=surnameid)
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
                )
            )

            relation_data = (
                ParentChildRelation.objects.filter(
                    Q(parent__surname__id=surnameid) and Q(child__surname__id=surnameid)
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
                        for j in data:
                            filtered_parent_results = filter(
                                lambda person: person["id"] == j["parent"], results
                            )
                            parent_relations = next(filtered_parent_results, None)
                            filtered_child_results = filter(
                                lambda person: person["id"] == j["child"], results
                            )
                            child_relations = next(filtered_child_results, None)
                            if child_relations["flag_show"] == True:
                                j["child"] = child_relations
                                j["parent"] = parent_relations
                                if j["parent"]["flag_show"] != True:
                                    j["parent"] = surname_relations
                                data2.append(j)

            return Response(data2, status=status.HTTP_200_OK)
        else:
            return Response([], status=status.HTTP_200_OK)

    def get_parent_child_relation(self, param, dictionary, lang):
        parent_child_relation = ParentChildRelation.objects.filter(
            Q(parent_id=param) | Q(child_id=param)
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
            relation = ParentChildRelation.objects.get(child=child)
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


class ProfileDetailView(APIView):

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


class ChildPerson(APIView):
    def get(self, request):
        try:
            person_id = request.GET.get("parent_id")
            lang = request.GET.get("lang", "en")
            child_ids = ParentChildRelation.objects.filter(
                parent=int(person_id)
            ).values_list("child", flat=True)
            children = Person.objects.filter(id__in=child_ids, is_deleted=False)
            child_data = PersonGetSerializer(
                children, many=True, context={"lang": lang}
            )
            return Response({"child_data": child_data.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"child_data": [], "Error": e},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            parent_id = request.data.get("parent_id")
            lang = request.data.get("lang", "en")
            name = request.data.get("child_name")
            dob = request.data.get("dob")
            platform = request.data.get("platform")
            person_data = Person.objects.get(id=parent_id, is_deleted=False)
            person_create = Person.objects.create(
                first_name=name,
                middle_name=person_data.first_name,
                surname=person_data.surname,
                date_of_birth=dob,
                address=person_data.address,
                mobile_number1="",
                mobile_number2="",
                out_of_address=person_data.out_of_address,
                city=person_data.city,
                state=person_data.state,
                child_flag=True,
                platform=platform,
            )
            person_child = ParentChildRelation.objects.create(
                parent=person_data, child=person_create, created_user=person_data
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

    def put(self, request):
        try:
            child_id = request.data.get("child_id")
            child_name = request.data.get("child_name")
            dob = request.data.get("dob")
            lang = request.data.get("lang", "en")
            person_data = Person.objects.get(id=child_id)
            if person_data:
                existing_profile = person_data.profile
                person_data.first_name = child_name
                person_data.date_of_birth = dob
                person_data.flag_show = False
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
                {"message": e}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request):
        try:
            lang = request.data.get("lang", "en")
            child_id = request.data.get("child_id")
            person = Person.objects.get(id=child_id)
            topmember = Surname.objects.get(id=person.surname.id)
            topmaember_id = topmember.top_member

            # Fetch the top member Person instance
            top_member_person = Person.objects.get(id=topmaember_id)

            parent_relation_data = ParentChildRelation.objects.filter(
                parent=person, is_deleted=False
            )
            if parent_relation_data:
                for data in parent_relation_data:
                    data.parent = top_member_person
                    data.save()

            relation_data = ParentChildRelation.objects.get(
                child=person, is_deleted=False
            )
            if relation_data:
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
            return Response(
                {"message": "Already Student Deleted"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AdminPersons(APIView):
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
        admin_persons = Person.objects.filter(
            Q(is_admin=True) | Q(is_super_admin=True)
        ).order_by("first_name")
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


def privacy_policy_app(request):
    return render(request, "privacy_policy.html")


def terms_condition_app(request):
    return render(request, "terms_condition.html")


class RelationtreeAPIView(APIView):

    def get(self, request):
        lang = request.GET.get("lang", "en")
        person_id = request.GET.get("person_id")

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
            person_data = (
                Person.objects.filter(
                    surname__id=surname, flag_show=True, is_deleted=False
                )
                .exclude(id__in=parent_data_id)
                .order_by("first_name")
            )
            serializer = PersonGetSerializer(
                person_data, many=True, context={"lang": lang}
            )

            return Response({"data": serializer.data})

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
