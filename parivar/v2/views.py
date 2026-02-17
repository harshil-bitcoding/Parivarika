from ..models import *
from ..serializers import *
from ..constants import encodedToken, decodedToken, getCurrentTimeInMilliseconds
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import NotFound
from logging import getLogger
import time
import hashlib
import string
from django.conf import settings
from django.http import Http404
from googletrans import Translator
from rest_framework.status import HTTP_201_CREATED, HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND, HTTP_200_OK, HTTP_401_UNAUTHORIZED
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from django.contrib.auth import authenticate
from django.db import transaction
from django.db import IntegrityError
from django.contrib.auth.hashers import make_password
from random import choices
import logging

logger = logging.getLogger(__name__)

def index(request):
    return HttpResponse("Hello, world. This is the index page.")

################################# Token Through API V2 version #################################

class LoginAPI(APIView):
    authentication_classes = []
    def post(self, request, pk=None):
        mobile_number = request.data.get('mobile_number')
        if not mobile_number:
            error_message = "Mobile number is required"
            return Response({'message': error_message}, status=status.HTTP_400_BAD_REQUEST)
        try:
            person = Person.objects.get(Q(mobile_number1=mobile_number) | Q(mobile_number2=mobile_number))
            token_key = encodedToken({
                "user_id" : person.id,
                "expires_in" : getCurrentTimeInMilliseconds() + (1000 * 60 * 60 * 24),
            })
            serializer = PersonSerializer(person)
            data = serializer.data
            data['token'] = token_key
            return Response(data, status=status.HTTP_200_OK)
        except Person.DoesNotExist:
            raise NotFound('User does not exist')
        
class SurnameDetailView(APIView):
    authentication_classes = []
    def get(self, request):
        surnames = Surname.objects.all()
        lang = request.GET.get('lang', 'en')
        serializer = SurnameSerializer(surnames, many=True, context={'lang': lang})        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request):
        surname_serializer = SurnameSerializer(data=request.data)
        if surname_serializer.is_valid():
            surname_instance = surname_serializer.save()
            person_data = {
                'first_name': surname_instance.name,
                'middle_name': surname_instance.name,
                'address': '',
                'blood_group': 1,
                'date_of_birth': datetime.today().strftime('%Y-%m-%d'),
                'out_of_country': 1,
                'out_of_address' : '',
                'city': 1,
                'state': 1,
                'mobile_number1': '',
                'mobile_number2': '',
                'surname': surname_instance.id,
                'flag_show': False,
                'is_admin': False,
                'is_registered_directly': True
            }
            person_serializer = PersonSerializer(data=person_data)
            if person_serializer.is_valid():
                person_instance = person_serializer.save()
                surname_instance.top_member = person_instance.id
                surname_instance.save()
                lang = request.data.get("lang", "en")
                if lang != "en":
                    guj_name = request.data.get("guj_name", request.data.get("name", ""))
                    if guj_name:
                        person_translate_data = {
                            'first_name': guj_name,
                            'person_id': person_instance.id,
                            'middle_name': guj_name,
                            'address': '',
                            'out_of_address' : '',
                            'language': lang
                        }
                        person_translate_serializer = TranslatePersonSerializer(data=person_translate_data)
                        if person_translate_serializer.is_valid():
                            person_translate_instance = person_translate_serializer.save()
                            return Response({'surname': surname_serializer.data}, status=status.HTTP_201_CREATED)
                        else:
                            surname_instance.delete()
                            person_instance.delete()
                            return Response(person_translate_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                return Response({'surname': surname_serializer.data}, status=status.HTTP_201_CREATED)
            else:
                surname_instance.delete()
                return Response(person_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(surname_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
class ParentChildRelationDetailView(APIView):
    authentication_classes = []
    def post(self, request):
        serializer = ParentChildRelationSerializer(data=request.data)
        if serializer.is_valid():
            parent_id = serializer.validated_data.get('parent_id')
            child_id = serializer.validated_data.get('child_id')            
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
                return Response({"error": "Invalid surname ID"}, status=status.HTTP_400_BAD_REQUEST)
            persons_surname_wise_list = Person.objects.filter(surname=surnameid).values_list('id', flat=True)
            if persons_surname_wise_list:
                relation_data = ParentChildRelation.objects.filter(
                    Q(parent__in=persons_surname_wise_list) | Q(child__in=persons_surname_wise_list)
                )
                if relation_data.exists():
                    lang = request.GET.get('lang', 'en')
                    data = GetParentChildRelationSerializer(relation_data, many=True, context={'lang': lang}).data
                    data = sorted(data, key=lambda x: (x["parent"]["id"], x["child"]["id"]))
                    return Response(data, status=status.HTTP_200_OK)
            return Response([], status=status.HTTP_200_OK)
        else:
            return Response([], status=status.HTTP_200_OK)  
    
    def get_parent_child_relation(self, param, dictionary, lang):
        parent_child_relation = ParentChildRelation.objects.filter(Q(parent_id=param) | Q(child_id=param))
        if parent_child_relation:
            serializer = GetParentChildRelationSerializer(parent_child_relation, many=True, context={'lang': lang})
            for child in serializer.data:
                tmp = None
                if len(dictionary) > 0:
                    for data in dictionary:
                        if int(child.get("child", None).get("id", None)) == int(data.get("child", None).get("id", None)) and int(data.get("parent", None).get("id", None)) == int(child.get("parent", None).get("id", None)) :
                            tmp = data
                            break
                if not tmp:
                    dictionary.append(child)
                    self.get_parent_child_relation(int(child.get("parent", None).get("id", None)), dictionary, lang)
                    self.get_parent_child_relation(int(child.get("child", None).get("id", None)), dictionary, lang)

class PersonBySurnameView(APIView):
    authentication_classes = []
    def post(self, request):
        surname = request.data.get('surname')
        lang = request.data.get('lang', 'en')
        if surname is None:
            return JsonResponse({'message': 'Surname ID is required', 'data': []}, status=400)
        surname_data = Surname.objects.filter(Q(id=int(surname)))
        if surname_data.exists(): 
            surname_data = surname_data.first()
            top_member = int(GetSurnameSerializer(surname_data).data.get("top_member", 0))
            persons = Person.objects.filter(Q(surname__id=int(surname))).exclude(id=top_member)
            if persons.exists(): 
                serializer = PersonGetSerializer(persons, many=True,  context={'lang': lang})
                if len(serializer.data) > 0 :
                    data = sorted(serializer.data, key=lambda x: (x["first_name"], x["middle_name"], x["surname"]))
                    return JsonResponse({'data': data})
        return JsonResponse({'data': []}, status=200)
    
class BloodGroupDetailView(APIView):
    authentication_classes = []
    def get(self, request):
        bloodgroup = BloodGroup.objects.all()
        serializer = BloodGroupSerializer(bloodgroup, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class ProfileDetailView(APIView):
    authentication_classes = []
    def post(self, request, id):
        try:
            try:
                id = int(id)
            except ValueError:
                return Response({'error': 'Invalid ID format'}, status=status.HTTP_400_BAD_REQUEST)
            person = get_object_or_404(Person, pk=id)
            serializer = ProfileSerializer(person, data=request.data)
            serializer.is_valid(raise_exception=True)
            profile = serializer.save()
            if 'profile_image' in request.FILES:
                profile.profile_image = request.FILES['profile_image']
                profile.save()
            return Response({'success': 'Profile data updated successfully!'}, status=status.HTTP_200_OK)
        except Person.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Error saving profile: {str(e)}'}, status=status.HTTP_400_BAD)
        
class PendingApproveDetailView(APIView):
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
        
class PersonDetailView(APIView):
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
        serializer = PersonSerializer(data=person_data)
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
            
        serializer = PersonSerializer(person, data=person_data, context={'person_id': person.id})
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
        
class AdminPersonDetailView(APIView):
    authentication_classes = []
    def get(self, request, pk, admin_uid):
        admin_user_id = admin_uid
        if not admin_user_id:
            return Response({'message': 'Missing Admin User in request data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        try:
            admin_person = Person.objects.get(pk=admin_user_id)
        except Person.DoesNotExist: 
            logger.error(f'Person with ID {admin_user_id} not found')
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
            logger.error(f'Person with ID {admin_user_id} not found')
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
        serializer = PersonSerializer(data=person_data)
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
            logger.error(f'Person with ID {admin_user_id} not found')
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


        
        print(mobile_number2)

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
        
        serializer = PersonSerializerV2(person, data=person_data, context={'person_id': person.id})
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
    

class BannerDetailView(APIView):
    authentication_classes = []
    def get(self, request):
        active_notifications = Banner.objects.filter(is_active=True)
        serializer = BannerSerializer(active_notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request):
        images = request.FILES.getlist('banner_images')
        for banner in images:
            serializer = BannerSerializer(data={
                            'title': request.data.get('title'),
                            'sub_title': request.data.get('sub_title'),
                            'image_url': banner,
                            'redirect_url': request.data.get('redirect_url')    
                        })
            if serializer.is_valid():
                serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def delete(self, request, pk):
        try:
            banner = get_object_or_404(Banner, pk=pk)
            banner.delete()
            return Response({"message": f"Banner record ID {pk} deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except Http404:
            return Response({"message": f"Banner record ID {pk} already deleted."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"message": f"Failed to delete the Banner record with ID {pk}: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
            print("Chiled -person -post --", request.data)
            parent_id = request.data.get("parent_id")
            lang = request.data.get("lang", "en")
            name = request.data.get("child_name")
            dob = request.data.get("dob")
            mobile_number = request.data.get("mobile_number") or ""
            platform = request.data.get("platform")
            person_data = Person.objects.get(id=parent_id, is_deleted=False)
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
                child_flag=True,
                platform=platform,
                update_field_message='newly created as child'
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
            print("Chiled -person -put --", request.data)
            child_id = request.data.get("child_id")
            child_name = request.data.get("child_name")
            dob = request.data.get("dob")
            mobile_number = request.data.get("mobile_number")
            lang = request.data.get("lang", "en")
            person_data = Person.objects.get(id=child_id)
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

