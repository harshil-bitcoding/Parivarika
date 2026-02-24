import io
import json
import mimetypes

from django.db.models import Q
from django.utils import timezone
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import Http404
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from datetime import datetime, timedelta
from notifications.models import Notification, NotificationImage, PersonPlayerId
from notifications.serializers import (
    NotificationCreateSerializer,
    NotificationNewGetSerializer,
    BirthdayPersonSerializer,
)
from notifications.time_conveter import convert_time_format
from parivar.models import Person, Surname
from notifications.tasks import notification_created
from notifications.helpers import get_birthday_queryset, split_birthdays
from parivar.utils import get_person_queryset
from parivar.v3.views import append_to_log
from PIL import Image


class NotificationDetailView(APIView):

    # def get(self, request):
    #     target_date = datetime.now()
    #     person_id = request.GET.get("person_id")
    #     is_event_show = request.GET.get("is_event_show","false").lower()

    #     today_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)

    #     today_end = target_date.replace(hour=23, minute=59, second=59, microsecond=59)

    #     if person_id:
    #         try:
    #             person = Person.objects.get(id=person_id, is_deleted=False)
    #         except Person.DoesNotExist:
    #             return Response(
    #                 {"message": "Person is Not Found"}, status=status.HTTP_404_NOT_FOUND
    #             )

    #         person_surename_ids = [person.surname.id]
    #         if is_event_show == "false":

    #             if (
    #                 person.flag_show == True
    #                 and person.is_admin == False
    #                 and person.is_super_admin == False
    #             ):
    #                 present_notification = Notification.objects.filter(
    #                     Q(start_date__lte=today_end),
    #                     Q(expire_date__gte=today_start),
    #                     to_person=person.id,
    #                     is_event=False,
    #                 ).order_by("expire_date")

    #                 past_notification = Notification.objects.filter(
    #                     Q(start_date__lt=today_start),
    #                     Q(expire_date__lt=today_start),
    #                     to_person=person.id,
    #                     is_event=False,
    #                 ).order_by("-expire_date")

    #                 pending_notification = Notification.objects.filter(
    #                     start_date__gte=today_end, is_event=False
    #                 )
    #             elif (
    #                 person.flag_show == True
    #                 and person.is_admin == True
    #                 and person.is_super_admin == False
    #             ):
    #                 present_notification = Notification.objects.filter(
    #                     Q(start_date__lte=today_end),
    #                     Q(expire_date__gte=today_start),
    #                     (
    #                         Q(filter__All=True)
    #                         | Q(
    #                             filter__surname__contains=[
    #                                 {"id": id} for id in person_surename_ids
    #                             ]
    #                         )
    #                     ),
    #                     is_event=False,
    #                 ).order_by("expire_date")

    #                 past_notification = Notification.objects.filter(
    #                     Q(start_date__lt=today_start),
    #                     Q(expire_date__lt=today_start),
    #                     (
    #                         Q(filter__All=True)
    #                         | Q(
    #                             filter__surname__contains=[
    #                                 {"id": id} for id in person_surename_ids
    #                             ]
    #                         )
    #                     ),
    #                     is_event=False,
    #                 ).order_by("-expire_date")

    #                 pending_notification = Notification.objects.filter(
    #                     start_date__gte=today_end, is_event=False
    #                 )
    #             elif (
    #                 person.flag_show == True
    #                 and person.is_admin == False
    #                 and person.is_super_admin == True
    #             ):
    #                 present_notification = Notification.objects.filter(
    #                     Q(start_date__lte=today_end),
    #                     Q(expire_date__gte=today_start),
    #                     is_event=False,
    #                 ).order_by("expire_date")

    #                 past_notification = Notification.objects.filter(
    #                     Q(start_date__lt=today_start),
    #                     Q(expire_date__lt=today_start),
    #                     is_event=False,
    #                 ).order_by("-expire_date")

    #                 pending_notification = Notification.objects.filter(
    #                     start_date__gte=today_end, is_event=False
    #                 )
    #         else:
    #             if (
    #                 person.flag_show == True
    #                 and person.is_admin == False
    #                 and person.is_super_admin == False
    #             ):
    #                 present_notification = Notification.objects.filter(
    #                     Q(start_date__lte=today_end),
    #                     Q(expire_date__gte=today_start),
    #                     to_person=person.id,
    #                     is_event=True,
    #                 ).order_by("expire_date")

    #                 past_notification = Notification.objects.filter(
    #                     Q(start_date__lt=today_start),
    #                     Q(expire_date__lt=today_start),
    #                     to_person=person.id,
    #                     is_event=True,
    #                 ).order_by("-expire_date")

    #                 pending_notification = Notification.objects.filter(
    #                     start_date__gte=today_end,
    #                     is_event=True,
    #                 )
    #             elif (
    #                 person.flag_show == True
    #                 and person.is_admin == True
    #                 and person.is_super_admin == False
    #             ):
    #                 present_notification = Notification.objects.filter(
    #                     Q(start_date__lte=today_end),
    #                     Q(expire_date__gte=today_start),
    #                     (
    #                         Q(filter__All=True)
    #                         | Q(
    #                             filter__surname__contains=[
    #                                 {"id": id} for id in person_surename_ids
    #                             ]
    #                         )
    #                     ),
    #                     is_event=True,
    #                 ).order_by("expire_date")

    #                 past_notification = Notification.objects.filter(
    #                     Q(start_date__lt=today_start),
    #                     Q(expire_date__lt=today_start),
    #                     (
    #                         Q(filter__All=True)
    #                         | Q(
    #                             filter__surname__contains=[
    #                                 {"id": id} for id in person_surename_ids
    #                             ]
    #                         )
    #                     ),
    #                     is_event=True,
    #                 ).order_by("-expire_date")

    #                 pending_notification = Notification.objects.filter(
    #                     start_date__gte=today_end,
    #                     is_event=True,
    #                 )
    #             elif (
    #                 person.flag_show == True
    #                 and person.is_admin == False
    #                 and person.is_super_admin == True
    #             ):
    #                 present_notification = Notification.objects.filter(
    #                     Q(start_date__lte=today_end),
    #                     Q(expire_date__gte=today_start),
    #                     is_event=True,
    #                 ).order_by("expire_date")

    #                 past_notification = Notification.objects.filter(
    #                     Q(start_date__lt=today_start),
    #                     Q(expire_date__lt=today_start),
    #                     is_event=True,
    #                 ).order_by("-expire_date")

    #                 pending_notification = Notification.objects.filter(
    #                     start_date__gte=today_end,
    #                     is_event=True,
    #                 )

    #         present_data = NotificationNewGetSerializer(present_notification, many=True)
    #         past_data = NotificationNewGetSerializer(past_notification, many=True)
    #         pending_data = NotificationNewGetSerializer(pending_notification, many=True)

    #         # ── Birthday data ─────────────────────────────────────────────
    #         birthday_context = {"request": request}
    #         try:
    #             base_qs = get_person_queryset(request)
    #             scoped_qs = get_birthday_queryset(person, base_qs)
    #             today_bdays, upcoming_bdays = split_birthdays(scoped_qs, login_person=person)
    #             birthday_data = {
    #                 "today": BirthdayPersonSerializer(
    #                     today_bdays, many=True, context=birthday_context
    #                 ).data,
    #                 "upcoming": BirthdayPersonSerializer(
    #                     upcoming_bdays, many=True, context=birthday_context
    #                 ).data,
    #             }
    #         except Exception:
    #             birthday_data = {"today": [], "upcoming": []}
    #         # ─────────────────────────────────────────────────────────────

    #         return Response(
    #             {
    #                 "present_notification": present_data.data,
    #                 "past_notification": past_data.data,
    #                 "pending_notification": (
    #                     pending_data.data
    #                     if person.is_admin or person.is_super_admin
    #                     else []
    #                 ),
    #                 # "birthday_data": birthday_data,
    #                 "today_birthday": BirthdayPersonSerializer(
    #                     today_bdays, many=True, context=birthday_context
    #                 ).data,
    #                 "upcoming_birthday": BirthdayPersonSerializer(
    #                     upcoming_bdays, many=True, context=birthday_context
    #                 ).data,
    #             },
    #             status=status.HTTP_200_OK,
    #         )

    #     return Response(
    #         {"message": "Please Enter a Person Details"},
    #         status=status.HTTP_400_BAD_REQUEST,
    #     )
    
    def get(self, request):
        target_date = datetime.now()
        person_id = request.GET.get("person_id")

        today_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)

        today_end = target_date.replace(hour=23, minute=59, second=59, microsecond=59)

        if person_id:
            try:
                person = Person.objects.get(id=person_id, is_deleted=False)
            except Person.DoesNotExist:
                return Response(
                    {"message": "Person is Not Found"}, status=status.HTTP_404_NOT_FOUND
                )

            person_surename_ids = [person.surname.id]
            if (
                person.flag_show == True
                and person.is_admin == False
                and person.is_super_admin == False
            ):
                present_notification = Notification.objects.filter(
                    Q(start_date__lte=today_end),
                    Q(expire_date__gte=today_start),
                    to_person=person.id,
                ).order_by("expire_date")

                past_notification = Notification.objects.filter(
                    Q(start_date__lt=today_start),
                    Q(expire_date__lt=today_start),
                    to_person=person.id,
                ).order_by("-expire_date")

                pending_notification = Notification.objects.filter(
                    start_date__gte=today_end, is_event=False
                )
            elif (
                person.flag_show == True
                and person.is_admin == True
                and person.is_super_admin == False
            ):
                present_notification = Notification.objects.filter(
                    Q(start_date__lte=today_end),
                    Q(expire_date__gte=today_start),
                    (
                        Q(filter__All=True)
                        | Q(
                            filter__surname__contains=[
                                {"id": id} for id in person_surename_ids
                            ]
                        )
                    ),
                ).order_by("expire_date")

                past_notification = Notification.objects.filter(
                    Q(start_date__lt=today_start),
                    Q(expire_date__lt=today_start),
                    (
                        Q(filter__All=True)
                        | Q(
                            filter__surname__contains=[
                                {"id": id} for id in person_surename_ids
                            ]
                        )
                    ),
                ).order_by("-expire_date")

                pending_notification = Notification.objects.filter(
                    start_date__gte=today_end, is_event=False
                )
            elif (
                person.flag_show == True
                and person.is_admin == False
                and person.is_super_admin == True
            ):
                present_notification = Notification.objects.filter(
                    Q(start_date__lte=today_end),
                    Q(expire_date__gte=today_start),
                ).order_by("expire_date")

                past_notification = Notification.objects.filter(
                    Q(start_date__lt=today_start),
                    Q(expire_date__lt=today_start),
                    is_event=False,
                ).order_by("-expire_date")

                pending_notification = Notification.objects.filter(
                    start_date__gte=today_end, is_event=False
                )
            # else:
            #     if (
            #         person.flag_show == True
            #         and person.is_admin == False
            #         and person.is_super_admin == False
            #     ):
            #         present_notification = Notification.objects.filter(
            #             Q(start_date__lte=today_end),
            #             Q(expire_date__gte=today_start),
            #             to_person=person.id,
            #             is_event=True,
            #         ).order_by("expire_date")

            #         past_notification = Notification.objects.filter(
            #             Q(start_date__lt=today_start),
            #             Q(expire_date__lt=today_start),
            #             to_person=person.id,
            #             is_event=True,
            #         ).order_by("-expire_date")

            #         pending_notification = Notification.objects.filter(
            #             start_date__gte=today_end,
            #             is_event=True,
            #         )
            #     elif (
            #         person.flag_show == True
            #         and person.is_admin == True
            #         and person.is_super_admin == False
            #     ):
            #         present_notification = Notification.objects.filter(
            #             Q(start_date__lte=today_end),
            #             Q(expire_date__gte=today_start),
            #             (
            #                 Q(filter__All=True)
            #                 | Q(
            #                     filter__surname__contains=[
            #                         {"id": id} for id in person_surename_ids
            #                     ]
            #                 )
            #             ),
            #             is_event=True,
            #         ).order_by("expire_date")

            #         past_notification = Notification.objects.filter(
            #             Q(start_date__lt=today_start),
            #             Q(expire_date__lt=today_start),
            #             (
            #                 Q(filter__All=True)
            #                 | Q(
            #                     filter__surname__contains=[
            #                         {"id": id} for id in person_surename_ids
            #                     ]
            #                 )
            #             ),
            #             is_event=True,
            #         ).order_by("-expire_date")

            #         pending_notification = Notification.objects.filter(
            #             start_date__gte=today_end,
            #             is_event=True,
            #         )
            #     elif (
            #         person.flag_show == True
            #         and person.is_admin == False
            #         and person.is_super_admin == True
            #     ):
            #         present_notification = Notification.objects.filter(
            #             Q(start_date__lte=today_end),
            #             Q(expire_date__gte=today_start),
            #             is_event=True,
            #         ).order_by("expire_date")

            #         past_notification = Notification.objects.filter(
            #             Q(start_date__lt=today_start),
            #             Q(expire_date__lt=today_start),
            #             is_event=True,
            #         ).order_by("-expire_date")

            #         pending_notification = Notification.objects.filter(
            #             start_date__gte=today_end,
            #             is_event=True,
            #         )

            present_data = NotificationNewGetSerializer(present_notification, many=True)
            past_data = NotificationNewGetSerializer(past_notification, many=True)
            pending_data = NotificationNewGetSerializer(pending_notification, many=True)

            # ── Birthday data ─────────────────────────────────────────────
            birthday_context = {"request": request}
            try:
                base_qs = get_person_queryset(request)
                scoped_qs = get_birthday_queryset(person, base_qs)
                today_bdays, upcoming_bdays = split_birthdays(scoped_qs, login_person=person)
            except Exception:
                today_bdays, upcoming_bdays = [], []

            # ── Facebook-style birthday card  ─────────────────────────────
            # "Amit Patel and 3 others have their birthday today."
            birthday_notification = None
            if today_bdays:
                first = today_bdays[0]
                others_count = len(today_bdays) - 1
                first_name = first.first_name or ""
                last_name  = first.surname.name if first.surname else ""
                full_name  = f"{first_name} {last_name}".strip()

                if others_count > 0:
                    message = (
                        f"{full_name} and {others_count} "
                        f"{'other' if others_count == 1 else 'others'} "
                        f"have their birthday today. Help them celebrate."
                    )
                else:
                    message = f"{full_name} has their birthday today. Help them celebrate."

                # Profile pic for the card (first person)
                card_profile = ""
                if first.thumb_profile:
                    try:
                        card_profile = first.thumb_profile.url
                    except Exception:
                        pass

                birthday_notification = {
                    "profile": card_profile,
                    "first_person_name": full_name,
                    "others_count": others_count,
                    "total_count": len(today_bdays),
                    "message": message,
                }
            # ── Merge birthday card as first item in present_notification ──
            present_list = list(present_data.data)
            if birthday_notification:
                present_list.insert(0, birthday_notification)
            # ─────────────────────────────────────────────────────────────

            return Response(
                {
                    "present_notification": present_list,
                    "past_notification": past_data.data,
                    "pending_notification": (
                        pending_data.data
                        if person.is_admin or person.is_super_admin
                        else []
                    ),
                    "today_birthday": BirthdayPersonSerializer(
                        today_bdays, many=True, context=birthday_context
                    ).data,
                    "upcoming_birthday": BirthdayPersonSerializer(
                        upcoming_bdays, many=True, context=birthday_context
                    ).data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {"message": "Please Enter a Person Details"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def post(self, request):
        title = request.data.get("title")
        sub_title = request.data.get("sub_title")
        image_url = request.FILES.getlist("image_url")
        person_id = request.data.get("person")
        include_player_ids = request.data.get("include_player_ids", "")
        is_show_left_time = request.data.get("is_show_left_time", False)
        is_all_segment = request.data.get("is_all_segment", "false").lower()
        redirect_url = request.data.get("redirect_url", "")

        is_event = False
        if "is_event" in request.data:
            is_event = request.data.get("is_event", "false").lower()
            if is_event == "true":
                is_event = True
            else:
                is_event = False

        is_show_ad_lable = False
        if "is_show_ad_lable" in request.data:
            is_show_ad_lable = request.data.get("is_show_ad_lable", "false").lower()
            if is_show_ad_lable == "true":
                is_show_ad_lable = True
            else:
                is_show_ad_lable = False
        player_ids_android = []
        player_ids_ios = []

        if "expire_date" in request.data:
            expire_date = request.data.get("expire_date")
            expire_date = convert_time_format(int(expire_date))
        else:
            return Response(
                {"message": "Expire date is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        event_reminder = None
        if "is_event_reminder" in request.data:
            event_reminder = request.data.get("is_event_reminder")
            event_reminder = convert_time_format(int(event_reminder))

        if "start_date" in request.data:
            start_date = request.data.get("start_date")
            start_date = convert_time_format(int(start_date))
        else:
            return Response(
                {"message": "Start date is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not title:
            return Response(
                {"message": "Title is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        if include_player_ids and is_all_segment == "false":

            if isinstance(include_player_ids, str):
                try:
                    include_player_ids = json.loads(include_player_ids)
                except json.JSONDecodeError:
                    return Response(
                        {"message": "Invalid format for include_player_ids"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            surnames = list(include_player_ids)
            player_ids_android = list(
                PersonPlayerId.objects.filter(
                    person__surname_id__in=surnames,
                    person__is_deleted=False,
                    platform="Android",
                ).values_list("player_id", flat=True)
            )

            player_ids_ios = list(
                PersonPlayerId.objects.filter(
                    person__surname_id__in=surnames, platform="Ios"
                ).values_list("player_id", flat=True)
            )
        if include_player_ids:
            if isinstance(include_player_ids, str):
                try:
                    include_player_ids = json.loads(include_player_ids)
                except json.JSONDecodeError:
                    return Response(
                        {"message": "Invalid format for include_player_ids"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        surname = []
        if is_all_segment != "true":
            surname_top_member_list = Surname.objects.filter(
                id__in=include_player_ids
            ).values_list("top_member", flat=True)

            surname_list = Surname.objects.filter(
                id__in=include_player_ids
            ).values_list("id", flat=True)

            surname_data = Surname.objects.filter(id__in=include_player_ids)
            for i in surname_data:
                surname.append({"id": i.id, "name": i.name})

        else:
            surname_top_member_list = Surname.objects.values_list(
                "top_member", flat=True
            )
            surname_list = Surname.objects.values_list("id", flat=True)

        surname_top_member_list = [int(x) for x in surname_top_member_list]

        to_persons = (
            Person.objects.filter(
                surname__id__in=surname_list, is_deleted=False, flag_show=True
            )
            .exclude(id__in=surname_top_member_list)
            .values_list("id", flat=True)
        )

        filter_field = {
            "surname": ([] if is_all_segment != "false" else surname),
            "All": True if is_all_segment != "false" else False,
        }

        notification_data = {
            "title": title,
            "sub_title": sub_title,
            "redirect_url": redirect_url,
            "start_date": start_date,
            "expire_date": expire_date,
            "to_person": to_persons,
            "is_event": is_event,
            "event_reminder_date": event_reminder,
            "created_user": person_id,
            "filter": filter_field,
            "is_show_left_time": is_show_left_time,
            "is_show_ad_lable": is_show_ad_lable,
        }

        serializer = NotificationCreateSerializer(data=notification_data)
        if serializer.is_valid():
            data = serializer.save()
            data_id = data.id
            if image_url:
                for file in image_url:
                    try:
                        mime_type, _ = mimetypes.guess_type(file.name)
                        if mime_type and mime_type.startswith("image"):
                            # image is Check a This is Png
                            img = Image.open(file)
                            if img.format != "PNG":
                                img = img.convert("RGBA")
                                png_image_io = io.BytesIO()
                                img.save(png_image_io, format="PNG")
                                png_image_io.seek(0)
                                image_name = f"{data_id}{file.name.split('.')[0]}.png"
                                image_file = InMemoryUploadedFile(
                                    png_image_io,
                                    None,
                                    image_name,
                                    "image/png",
                                    png_image_io.getbuffer().nbytes,
                                    None,
                                )
                            else:
                                # Image is already PNG, use the uploaded file directly
                                image_file = file
                        else:
                            # If not an image, use the file as is
                            image_file = file

                        # Save the file or Image
                        NotificationImage.objects.create(
                            notification_id_id=data_id, image_url=image_file
                        )
                    except IOError:
                        return Response(
                            {"message": "Invalid file."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
            notifiy_image = (
                NotificationImage.objects.filter(notification_id_id=data_id)
                .values_list("image_url", flat=True)
                .first()
            )
            image_url = notifiy_image
            sender = "Notification"
            start_date = datetime.fromisoformat(start_date)
            start_date = timezone.make_aware(
                start_date, timezone.get_default_timezone()
            )
            start_date = timezone.localtime(start_date).date()
            today = datetime.now().date()
            if str(start_date) == str(today):
                notification_created.delay(
                    sender,
                    title,
                    sub_title,
                    image_url,
                    is_all_segment,
                    player_ids_android,
                    player_ids_ios,
                )
                pass

            return Response(
                {
                    "notification_data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        try:
            notification = get_object_or_404(Notification, pk=pk)
            notification.delete()
            return Response(
                {"message": f"Notification record ID {pk} deleted successfully."},
                status=status.HTTP_204_NO_CONTENT,
            )
        except Http404:
            return Response(
                {"message": f"Notification record ID {pk} already deleted."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {
                    "message": f"Failed to delete the Notification record with ID {pk}: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CreatePlayerId(APIView):
    def post(self, request):
        person_id = request.data.get("person_id", "")
        player_id = request.data.get("player_id", "")
        is_ios_platform = request.data.get("is_ios_platform", False)
        try:
            person = Person.objects.get(id=person_id, is_deleted=False)
        except Person.DoesNotExist:
            return Response(
                {"message": "Person not found"}, status=status.HTTP_404_NOT_FOUND
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
        return Response({"message": "okay"}, status=status.HTTP_200_OK)


class NotificationDeleteView(APIView):
    def delete(self, request):
        notification_id = request.data.get("notification_id")
        person_id = request.data.get("person_id")

        if not notification_id or not person_id:
            return Response(
                {"message": "Notification ID and Person ID are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            notification = Notification.objects.get(id=notification_id, is_event=False)
        except Notification.DoesNotExist:
            return Response(
                {"message": "Notification not found"}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            person = Person.objects.get(id=person_id)
        except Person.DoesNotExist:
            return Response(
                {"message": "Person not found"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            if person not in notification.to_person.all():
                return Response(
                    {"message": "Person is not associated with this notification"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            notification.to_person.remove(person_id)
            notification.save()

            return Response(
                {"message": "Notification updated successfully"},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response({"message": f"{e}"})


class EventFrequency(APIView):
    def get(self, request):
        today = datetime.now()
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today.replace(hour=23, minute=59, second=59, microsecond=59)

        one_week_end = (today + timedelta(weeks=1)).replace(
            hour=23, minute=59, second=59, microsecond=59
        )

        one_month_end = (today + timedelta(days=30)).replace(
            hour=23, minute=59, second=59, microsecond=59
        )

        six_months_end = (today + timedelta(days=6 * 30)).replace(
            hour=23, minute=59, second=59, microsecond=59
        )

        def process_notifications(notifications):
            player_ids_android = []
            player_ids_ios = []

            for notification in notifications:
                notification_image = (
                    NotificationImage.objects.filter(
                        notification_id_id=notification.id, is_event=True
                    )
                    .values_list("image_url", flat=True)
                    .first()
                )

                if notification.filter.get("All") == False:
                    is_all_segment = "false"
                    surnames = notification.filter.get("surname")
                    player_ids_android = list(
                        PersonPlayerId.objects.filter(
                            person__surname__name__in=surnames,
                            person__is_deleted=False,
                            platform="Android",
                        ).values_list("player_id", flat=True)
                    )
                    player_ids_ios = list(
                        PersonPlayerId.objects.filter(
                            person__surname__name__in=surnames,
                            person__is_deleted=False,
                            platform="Ios",
                        ).values_list("player_id", flat=True)
                    )
                else:
                    is_all_segment = "true"

                notification_created.delay(
                    "Notification",
                    notification.title,
                    notification.sub_title,
                    notification_image,
                    is_all_segment,
                    player_ids_android,
                    player_ids_ios,
                )

            return (
                NotificationNewGetSerializer(notifications, many=True).data
                if notifications
                else []
            )

        one_week_before_serializer = []
        one_week_after_serializer = []

        one_week_before_notifications = Notification.objects.filter(
            start_date__lte=today_end,
            expire_date__range=[today_end, one_week_end],
            is_event=True,
        )
        one_week_before_serializer = process_notifications(
            one_week_before_notifications
        )

        if today.weekday() == 0:
            one_week_after_notifications = Notification.objects.filter(
                start_date__lte=today_end,
                expire_date__range=[one_week_end, one_month_end],
                is_event=True,
            )
            one_week_after_serializer = process_notifications(
                one_week_after_notifications
            )

        return Response(
            {
                "one_week_before_notifications": one_week_before_serializer,
                "one_week_after_notifications": one_week_after_serializer,
            }
        )


class PendingNotificationSend(APIView):
    def get(self, request):
        try:
            # Log the start time
            now = datetime.now()
            filename = "cronlog.log"
            message = f"\nstart pending notification send time :- {now}"
            append_to_log(filename, message)

            # Define target datetime
            target_date = datetime.now()
            today_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = target_date.replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
            player_ids_android = []
            player_ids_ios = []
            # Query notifications
            notifications = Notification.objects.filter(
                start_date__range=(today_start, today_end)
            ).order_by("id")

            # Process notifications
            for i in notifications:
                notification_image = (
                    NotificationImage.objects.filter(notification_id_id=i.id)
                    .values_list("image_url", flat=True)
                    .first()
                )

                if i.filter.get("All") == False:
                    is_all_segment = "false"
                    surnames = i.filter.get("surname")
                    player_ids_android = list(
                        PersonPlayerId.objects.filter(
                            person__surname__name__in=surnames,
                            person__is_deleted=False,
                            platform="Android",
                        ).values_list("player_id", flat=True)
                    )

                    player_ids_ios = list(
                        PersonPlayerId.objects.filter(
                            person__surname__name__in=surnames, platform="Ios"
                        ).values_list("player_id", flat=True)
                    )
                else:
                    is_all_segment = "true"

                image_url = notification_image
                sender = "Notification"

                task_args = (
                    sender,
                    i.title,
                    i.sub_title,
                    image_url,
                    is_all_segment,
                    player_ids_android,
                    player_ids_ios,
                )
                try:
                    notification_created.delay(*task_args)
                except Exception:
                    # Redis unavailable — run synchronously (local dev / no broker)
                    notification_created(*task_args)

            # Log end time
            now = datetime.now()
            filename = "cronlog.log"
            message = f"End pending notification send time :- {now}"
            append_to_log(filename, message)

            return Response("okay", status=status.HTTP_200_OK)

        except Exception as e:
            now = datetime.now()
            filename = "cronlog.log"
            message = f"End pending notification send time :- {now} \n Error is :- {e}"
            append_to_log(filename, message)
            return Response(
                {"message": f"Error Sending Pending Notification: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ---------------------------------------------------------------------------
# Birthday API
# ---------------------------------------------------------------------------

class BirthdayAPIView(APIView):
    """
    GET /api/v4/birthdays?person_id=<id>&lang=<en|guj>

    Returns today's and upcoming (next-7-day) birthdays scoped to the
    requesting person's role:
        - Normal member  → same samaj
        - Admin          → same samaj + same surname
        - Super Admin    → entire village (all samaj)

    Query Params:
        person_id (int, required): ID of the requesting person.
        lang      (str, optional): "en" (default) or "guj"
                                   — reserved for future use.

    Response:
        {
            "today_birthdays":    [ ...BirthdayPersonSerializer... ],
            "upcoming_birthdays": [ ...BirthdayPersonSerializer... ]
        }
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        from parivar.utils import get_person_queryset
        from notifications.helpers import get_birthday_queryset, split_birthdays
        from notifications.serializers import BirthdayPersonSerializer

        person_id = request.GET.get("person_id")
        if not person_id:
            return Response(
                {"message": "person_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch requesting person (respects demo-mode via get_person_queryset)
        try:
            person = get_person_queryset(request).select_related(
                "surname", "samaj", "samaj__village"
            ).get(pk=person_id)
        except Person.DoesNotExist:
            return Response(
                {"message": "Person not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not person.flag_show:
            return Response(
                {"message": "Person is not approved yet"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Base queryset (already demo / deleted filtered)
        base_qs = get_person_queryset(request)

        # Apply role-based scoping
        scoped_qs = get_birthday_queryset(person, base_qs)

        # Split into today & upcoming (surname-priority sort applied)
        today_list, upcoming_list = split_birthdays(scoped_qs, login_person=person)

        return Response(
            {
                "today_birthdays": BirthdayPersonSerializer(
                    today_list, many=True, context={"request": request}
                ).data,
                "upcoming_birthdays": BirthdayPersonSerializer(
                    upcoming_list, many=True, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Birthday Cron Send API  
# ---------------------------------------------------------------------------

class BirthdaySendView(APIView):
    """
    GET /api/v4/send-birthday-notifications

    Finds every person whose birthday (MM-DD portion of date_of_birth)
    matches TODAY's date, then sends an individual push notification to
    all members of that person's samaj via the existing OneSignal /
    Celery pipeline.

    Designed to be called once daily at 12:00 AM by a system cron:

        0 0 * * * curl -s http://localhost:8000/api/v4/send-birthday-notifications \
                       >> /var/log/birthday_cron.log 2>&1

    No authentication required (called by server-side cron).
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        from datetime import date as _date

        today_md = _date.today().strftime("%m-%d")  # e.g. "02-24"

        log_file = "birthday_cron.log"
        now = datetime.now()
        append_to_log(log_file, f"\n[{now}] Birthday cron started — matching MM-DD = {today_md}")

        # ── 1. Find today's birthday persons (real data only, not demo) ──
        all_persons = (
            Person.objects.filter(is_deleted=False, is_demo=False, flag_show=True)
            .select_related("surname", "samaj")
            .only(
                "id", "first_name", "middle_name", "date_of_birth",
                "surname", "samaj",
            )
        )

        birthday_persons = [
            p for p in all_persons
            if (p.date_of_birth or "").strip()[5:10] == today_md
        ]

        append_to_log(
            log_file,
            f"[{now}] Found {len(birthday_persons)} birthday person(s) today.",
        )

        if not birthday_persons:
            return Response(
                {
                    "message": "No birthdays today.",
                    "birthday_persons_found": 0,
                    "notifications_sent": 0,
                },
                status=status.HTTP_200_OK,
            )

        # ── 2. For each birthday person, notify their samaj members ──────
        notifications_sent = 0

        for bday_person in birthday_persons:
            if not bday_person.samaj_id:
                append_to_log(
                    log_file,
                    f"  Skipped person id={bday_person.id} — no samaj assigned.",
                )
                continue

            # Build notification title & body
            surname_name = bday_person.surname.name if bday_person.surname else ""
            title = "🎂 Today's Birthday!"
            body = (
                f"Wish {bday_person.first_name} {bday_person.middle_name or ''} "
                f"{surname_name} a very Happy Birthday! 🎉"
            ).strip()

            # Collect samaj members' player IDs (exclude the birthday person)
            android_ids = list(
                PersonPlayerId.objects.filter(
                    person__samaj_id=bday_person.samaj_id,
                    person__is_deleted=False,
                    person__flag_show=True,
                    platform="Android",
                )
                .exclude(person_id=bday_person.pk)
                .values_list("player_id", flat=True)
            )

            ios_ids = list(
                PersonPlayerId.objects.filter(
                    person__samaj_id=bday_person.samaj_id,
                    person__is_deleted=False,
                    person__flag_show=True,
                    platform="Ios",
                )
                .exclude(person_id=bday_person.pk)
                .values_list("player_id", flat=True)
            )

            if not android_ids and not ios_ids:
                append_to_log(
                    log_file,
                    f"  Skipped person id={bday_person.pk} — no registered devices in samaj.",
                )
                continue

            # Dispatch via existing Celery task.
            # Falls back to synchronous execution when Redis/Celery is not
            # running (e.g. local dev), so the endpoint never 500s.
            task_args = (
                "BirthdayNotification",  # sender
                title,
                body,
                None,                    # no image
                "false",                 # is_all_segment = false (targeted)
                android_ids,
                ios_ids,
            )
            try:
                notification_created.delay(*task_args)
            except Exception:
                # Redis unavailable — run synchronously (local dev / no broker)
                notification_created(*task_args)

            notifications_sent += 1
            append_to_log(
                log_file,
                f"  Sent for person id={bday_person.pk} "
                f"({len(android_ids)} Android, {len(ios_ids)} iOS devices).",
            )

        # ── 3. Summary log & response ─────────────────────────────────────
        end_time = datetime.now()
        append_to_log(
            log_file,
            f"[{end_time}] Birthday cron done — "
            f"{notifications_sent}/{len(birthday_persons)} notifications dispatched.\n",
        )

        return Response(
            {
                "message": f"Birthday notifications dispatched for {notifications_sent} person(s).",
                "birthday_persons_found": len(birthday_persons),
                "notifications_sent": notifications_sent,
            },
            status=status.HTTP_200_OK,
        )
