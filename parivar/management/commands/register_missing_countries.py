import json
import re
import urllib.request

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import models
from django.utils.text import slugify

from parivar.models import Country


def _norm(value: str) -> str:
    value = value.lower().strip()
    value = value.replace("&", " and ")
    value = value.replace("'", "")
    value = value.replace(".", " ")
    value = value.replace("-", " ")
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _dial_code(idd: dict) -> str | None:
    root = (idd.get("root") or "").strip()
    suffixes = [str(s).strip() for s in (idd.get("suffixes") or []) if str(s).strip()]
    if not root:
        return None
    if not suffixes:
        return root
    if root in ("+1", "+7"):
        return root
    if len(suffixes) == 1:
        return f"{root}{suffixes[0]}"
    pick = sorted(suffixes, key=lambda x: (-len(x), x))[0]
    return f"{root}{pick}"


class Command(BaseCommand):
    help = (
        "Register missing countries in DB with name, guj_name, country_code and flag "
        "from restcountries dataset."
    )

    def handle(self, *args, **options):
        normalize_guj = options.get("normalize_guj_name", False)

        url = "https://restcountries.com/v3.1/all?fields=name,idd,flags"
        with urllib.request.urlopen(url, timeout=30) as response:
            countries = json.loads(response.read().decode("utf-8"))

        # Keep naming compatible with your existing DB naming style.
        name_overrides = {
            "United States": "United States America",
            "Czechia": "Czech Republic (Czechia)",
            "Palestine": "State of Palestine",
            "São Tomé and Príncipe": "Sao Tome & Principe",
            "Saint Vincent and the Grenadines": "St. Vincent & Grenadines",
            "Democratic Republic of the Congo": "DR Congo",
            "Ivory Coast": "Côte d'Ivoire",
            "Vatican City": "Holy See",
            "Cape Verde": "Cabo Verde",
        }

        existing_by_name = {_norm(c.name): c for c in Country.objects.all()}

        created = 0
        skipped = 0
        updated_country_code = 0
        updated_flag = 0
        failed_flag = 0

        for item in countries:
            common_name = (item.get("name") or {}).get("common")
            if not common_name:
                skipped += 1
                continue

            db_name = name_overrides.get(common_name, common_name)
            key = _norm(db_name)

            code = _dial_code(item.get("idd") or {})
            if not code:
                skipped += 1
                continue

            country = existing_by_name.get(key)
            if country is None:
                country = Country.objects.create(
                    name=db_name,
                    guj_name=None,
                    country_code=code,
                )
                existing_by_name[key] = country
                created += 1
            else:
                changed_fields = []
                if not country.country_code:
                    country.country_code = code
                    changed_fields.append("country_code")
                    updated_country_code += 1
                if changed_fields:
                    country.save(update_fields=changed_fields)

            flag_url = (item.get("flags") or {}).get("png")
            if flag_url and not country.flag:
                try:
                    with urllib.request.urlopen(flag_url, timeout=30) as flag_response:
                        flag_bytes = flag_response.read()
                    filename = f"country_{slugify(db_name)}.png"
                    country.flag.save(filename, ContentFile(flag_bytes), save=True)
                    updated_flag += 1
                except Exception:
                    failed_flag += 1

        normalized = 0
        if normalize_guj:
            normalized = Country.objects.filter(guj_name__isnull=False, guj_name=models.F("name")).update(guj_name=None)

        self.stdout.write(self.style.SUCCESS(f"Created missing countries: {created}"))
        self.stdout.write(self.style.SUCCESS(f"Skipped existing/invalid: {skipped}"))
        self.stdout.write(self.style.SUCCESS(f"Updated missing country_code: {updated_country_code}"))
        self.stdout.write(self.style.SUCCESS(f"Updated missing flags: {updated_flag}"))
        if normalize_guj:
            self.stdout.write(self.style.SUCCESS(f"Normalized guj_name rows: {normalized}"))
        if failed_flag:
            self.stdout.write(self.style.WARNING(f"Flag download failed for: {failed_flag}"))

    def add_arguments(self, parser):
        parser.add_argument(
            "--normalize-guj-name",
            action="store_true",
            help="Set guj_name to empty (NULL) where guj_name is same as English name.",
        )
