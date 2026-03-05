import json
import re
import urllib.request

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import Q

from parivar.models import Country


def _norm(value: str) -> str:
    value = (value or "").lower().strip()
    value = value.replace("&", " and ")
    value = value.replace("'", "")
    value = value.replace(".", " ")
    value = value.replace("-", " ")
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _format_lengths(lengths) -> str:
    uniq = sorted({int(x) for x in lengths if str(x).isdigit()})
    if not uniq:
        return ""
    if len(uniq) == 1:
        return str(uniq[0])
    return ",".join(str(x) for x in uniq)


class Command(BaseCommand):
    help = (
        "Fill Country.mobile_number_length using libphonenumber metadata "
        "(real country-wise supported mobile lengths)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Update all rows even if mobile_number_length already exists.",
        )
        parser.add_argument(
            "--default-length",
            type=str,
            default="10",
            help="Fallback value when a country cannot be mapped (default: 10).",
        )

    def handle(self, *args, **options):
        force = options["force"]
        default_length = options["default_length"].strip()

        try:
            import phonenumbers
            from phonenumbers.phonemetadata import PhoneMetadata
        except Exception as exc:
            raise CommandError(
                "Missing dependency 'phonenumbers'. Install it first:\n"
                "pip install phonenumbers"
            ) from exc

        # Ensure DB column exists even if migration is not applied yet.
        table = Country._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                f"ALTER TABLE {table} "
                "ADD COLUMN IF NOT EXISTS mobile_number_length varchar(20);"
            )

        # Build name -> region (ISO2) map from REST Countries.
        url = "https://restcountries.com/v3.1/all?fields=name,cca2,altSpellings"
        with urllib.request.urlopen(url, timeout=30) as response:
            countries = json.loads(response.read().decode("utf-8"))

        name_to_region = {}
        for item in countries:
            region = (item.get("cca2") or "").upper().strip()
            if len(region) != 2:
                continue
            names = set()
            name_obj = item.get("name") or {}
            if name_obj.get("common"):
                names.add(name_obj["common"])
            if name_obj.get("official"):
                names.add(name_obj["official"])
            for alt in (item.get("altSpellings") or []):
                names.add(alt)
            for n in names:
                name_to_region[_norm(n)] = region

        aliases = {
            "united states america": "US",
            "dr congo": "CD",
            "congo": "CG",
            "czech republic czechia": "CZ",
            "state of palestine": "PS",
            "sao tome and principe": "ST",
            "st vincent and grenadines": "VC",
            "saint kitts and nevis": "KN",
            "cote divoire": "CI",
            "holy see": "VA",
            "cabo verde": "CV",
        }

        qs = Country.objects.all().order_by("id")
        if not force:
            qs = qs.filter(Q(mobile_number_length__isnull=True) | Q(mobile_number_length=""))

        updated = 0
        fallbacked = 0
        failed = 0

        for country in qs:
            key = _norm(country.name)
            region = aliases.get(key) or name_to_region.get(key)

            length_value = ""
            if region:
                metadata = PhoneMetadata.metadata_for_region(region, None)
                if metadata:
                    mobile_lengths = list(getattr(metadata.mobile, "possible_length", []) or [])
                    if not mobile_lengths:
                        mobile_lengths = list(getattr(metadata.general_desc, "possible_length", []) or [])
                    length_value = _format_lengths(mobile_lengths)

            if not length_value:
                length_value = default_length
                fallbacked += 1

            try:
                if country.mobile_number_length != length_value:
                    country.mobile_number_length = length_value
                    country.save(update_fields=["mobile_number_length"])
                    updated += 1
            except Exception:
                failed += 1

        self.stdout.write(self.style.SUCCESS(f"Updated rows: {updated}"))
        self.stdout.write(self.style.SUCCESS(f"Fallback rows: {fallbacked}"))
        if failed:
            self.stdout.write(self.style.WARNING(f"Failed rows: {failed}"))

