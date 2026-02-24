"""
Birthday helper functions for Bila Parivar.

Provides reusable, role-aware queryset scoping and
today / upcoming (next-7-days) birthday splitting.

Person.date_of_birth is a CharField in the format:
    "YYYY-MM-DD HH:MM:SS.SSS"  (e.g. "1990-02-24 00:00:00.000")
So birthday matching is done on the MM-DD slice [5:10].
"""

from datetime import date, timedelta


# ---------------------------------------------------------------------------
# Role-based scoping
# ---------------------------------------------------------------------------

def get_birthday_queryset(person, base_qs):
    """
    Scope *base_qs* (already filtered for is_demo / is_deleted) to the
    persons that *person* is allowed to see birthdays for, based on their role.

    Roles (mirror the Notification API visibility logic):
        Super Admin  → every person in the same village (across all samaj)
        Admin        → same samaj + same surname
        Normal member→ same samaj only

    The requesting person themselves is always excluded.

    Args:
        person (Person): The authenticated / requesting person object.
        base_qs (QuerySet): Pre-filtered Person queryset
                            (e.g. from get_person_queryset(request)).

    Returns:
        QuerySet: Scoped Person queryset, flag_show=True, excl. *person*.
    """
    qs = base_qs.filter(flag_show=True).exclude(pk=person.pk)

    if person.is_super_admin:
        # Super admin: entire village (all samaj under same village)
        if person.samaj and person.samaj.village_id:
            qs = qs.filter(samaj__village_id=person.samaj.village_id)
        else:
            # Fallback: only own samaj if village unknown
            qs = qs.filter(samaj=person.samaj)

    elif person.is_admin:
        # Admin: same samaj + same surname
        qs = qs.filter(
            samaj=person.samaj,
            surname=person.surname,
        )

    else:
        # Normal member: same samaj only
        qs = qs.filter(samaj=person.samaj)

    return qs


# ---------------------------------------------------------------------------
# Birthday splitting — today vs. next 7 days
# ---------------------------------------------------------------------------

def _next_seven_md_strings(today):
    """
    Return a list of 7 MM-DD strings for the 7 days AFTER today
    (day+1 through day+7), correctly wrapping across year boundaries.

    Args:
        today (date): Reference date.

    Returns:
        list[str]: Ordered list like ["02-25", "02-26", ..., "03-03"]
    """
    return [
        (today + timedelta(days=1)).strftime("%m-%d")
        # for i in range(1, 8)
    ]


def split_birthdays(scoped_qs, login_person=None):
    """
    Split a scoped Person queryset into today's and upcoming (next-7-day)
    birthdays using the MM-DD portion of date_of_birth.

    Records with a null / empty / un-parseable date_of_birth are skipped
    silently.

    Sorting rules
    -------------
    * **today_birthdays** — login person's surname first, then alphabetically
      by first_name within each surname group.
    * **upcoming_birthdays** — nearest date first; within the same date,
      login person's surname first, then first_name alphabetically.

    Args:
        scoped_qs   (QuerySet): Role-scoped Person queryset.
        login_person (Person):  The requesting person (used for surname
                                priority sorting). Pass ``None`` to disable.

    Returns:
        tuple:
            today_list     (list[Person]) — birthdays today
            upcoming_list  (list[Person]) — birthdays in next 7 days
    """
    today = date.today()
    today_md   = today.strftime("%m-%d")            # e.g. "02-24"
    upcoming_mds = _next_seven_md_strings(today)    # e.g. ["02-25", ..., "03-03"]
    upcoming_order = {md: idx for idx, md in enumerate(upcoming_mds)}

    # Surname id of the login person — used as a sort priority key
    login_surname_id = (
        login_person.surname_id
        if login_person and login_person.surname_id
        else None
    )

    def surname_sort_key(person):
        """
        0 if same surname as login person (surfaces first),
        1 otherwise.
        """
        if login_surname_id and person.surname_id == login_surname_id:
            return 0
        return 1

    # Only fetch fields needed for matching + serialization
    persons = scoped_qs.select_related("surname", "samaj").only(
        "id", "first_name", "middle_name", "date_of_birth",
        "surname", "samaj", "flag_show", "profile", "thumb_profile",
    )

    today_list = []
    upcoming_unsorted = []  # list of (date_pos, surname_priority, first_name, person)

    for person in persons:
        dob = (person.date_of_birth or "").strip()
        if not dob or len(dob) < 10:
            continue  # skip blank / malformed DOB

        person_md = dob[5:10]  # "MM-DD" slice

        if person_md == today_md:
            today_list.append(person)
        elif person_md in upcoming_order:
            upcoming_unsorted.append((
                upcoming_order[person_md],   # primary:  nearest date first
                surname_sort_key(person),    # secondary: same surname first
                (person.first_name or "").lower(),  # tertiary: alphabetical
                person,
            ))

    # ── Today: same surname first, then first_name alphabetical ──────────
    today_list.sort(key=lambda p: (
        surname_sort_key(p),
        (p.first_name or "").lower(),
    ))

    # ── Upcoming: (date asc, same-surname first, first_name asc) ─────────
    upcoming_unsorted.sort(key=lambda t: (t[0], t[1], t[2]))
    upcoming_list = [t[3] for t in upcoming_unsorted]

    return today_list, upcoming_list
