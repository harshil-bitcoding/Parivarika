from datetime import datetime
from celery import shared_task
import requests
import json
import os


def append_to_log(filename, message):
    """Append a message to an existing log file, creating the file if it doesn't exist."""
    with open(filename, "a") as file:
        file.write(message + "\n")


@shared_task
def notification_created(
    sender,
    title,
    sub_title,
    image_url,
    is_all_segment,
    player_ids_android=None,
    player_ids_ios=None,
):
    now = datetime.now()
    filename = "celery.log"
    message = f"\nstart celery notification send time :- {now}"
    append_to_log(filename, message)
    # Android notification
    image_full_url = ""

    if image_url:
        image_full_url = (
            f"https://classdekho.s3.ap-south-1.amazonaws.com/Billaparivar/{image_url}"
        )

    url = "https://onesignal.com/api/v1/notifications"

    if is_all_segment != "false":

        payload = json.dumps(
            {
                "app_id": os.getenv("ANDROID_ONE_SIGNAL_APP_ID"),
                "included_segments": ["All"],
                "headings": {"en": title},
                "contents": {"en": sub_title if sub_title else ""},
                "big_picture": image_full_url,
            }
        )

    else:

        payload = json.dumps(
            {
                "app_id": os.getenv("ANDROID_ONE_SIGNAL_APP_ID"),
                "include_player_ids": player_ids_android,
                "headings": {"en": title},
                "contents": {"en": sub_title if sub_title else ""},
                "big_picture": image_full_url,
            }
        )

    headers = {
        "Authorization": os.getenv("ANDROID_ONE_SIGNAL_AUTHORIZATION_ID"),
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, data=payload)
    message = f"Response :- {response.text}"
    if response.status_code != 200:
        message = f"Response Error :- {response.text}"
    append_to_log(filename, message)
    # iOS notification
    if is_all_segment != "false":

        payload = json.dumps(
            {
                "app_id": os.getenv("IOS_ONE_SIGNAL_APP_ID"),
                "headings": {"en": title if title else "Bila Parivar"},
                "contents": {"en": sub_title if sub_title else ""},
                "included_segments": ["All"],
                "big_picture": image_full_url,
                "ios_badgeCount": 1,
                "ios_badgeType": "Increase",
            }
        )

    else:

        payload = json.dumps(
            {
                "app_id": os.getenv("IOS_ONE_SIGNAL_APP_ID"),
                "headings": {"en": title if title else "Bila Parivar"},
                "contents": {"en": sub_title if sub_title else ""},
                "include_player_ids": player_ids_ios,
                "big_picture": image_full_url,
                "ios_badgeCount": 1,
                "ios_badgeType": "Increase",
            }
        )

    headers = {
        "Authorization": os.getenv("IOS_ONE_SIGNAL_AUTHORIZATION_ID"),
        "Content-Type": "application/json",
        "Cookie": "__cf_bm=5LdmNasmbo8fgB1DrbNd5lm6Gq_pCZ3LYwu4zAvoQAs-1716875406-1.0.1.1-XsyawWvQvRMpi9DNiWiGyLphXwziSoiXNzYcNwq6SFMpsKnMD1_wBi7VOSn38F4J6lOdbcceH24KgRKIshs1dQ",
    }
    response = requests.post(url, headers=headers, data=payload)
    message = f"Response :- {response.text}"
    append_to_log(filename, message)
    now = datetime.now()
    message = f"\n end celery notification send time :- {now}"
    append_to_log(filename, message)
