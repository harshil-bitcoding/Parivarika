import json
import re
import urllib.request

from django.core.management.base import BaseCommand

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


class Command(BaseCommand):
    help = "Populate Country.country_code with real international dialing codes."

    def handle(self, *args, **options):
        url = "https://restcountries.com/v3.1/all?fields=name,idd,altSpellings"
        with urllib.request.urlopen(url, timeout=30) as response:
            countries = json.loads(response.read().decode("utf-8"))

        lookup = {}
        for country in countries:
            idd = country.get("idd") or {}
            root = (idd.get("root") or "").strip()
            suffixes = [str(s).strip() for s in (idd.get("suffixes") or []) if str(s).strip()]
            if not root:
                continue

            if suffixes:
                if root in ("+1", "+7"):
                    code = root
                elif len(suffixes) == 1:
                    code = f"{root}{suffixes[0]}"
                else:
                    pick = sorted(suffixes, key=lambda x: (-len(x), x))[0]
                    code = f"{root}{pick}"
            else:
                code = root

            names = set()
            name = country.get("name") or {}
            if name.get("common"):
                names.add(name["common"])
            if name.get("official"):
                names.add(name["official"])
            for alt in (country.get("altSpellings") or []):
                names.add(alt)

            for n in names:
                lookup[_norm(n)] = code

        aliases = {
            "united states america": "united states",
            "dr congo": "democratic republic of the congo",
            "congo": "republic of the congo",
            "czech republic czechia": "czechia",
            "state of palestine": "palestine",
            "sao tome and principe": "sao tome and principe",
            "st vincent and grenadines": "saint vincent and the grenadines",
            "saint kitts and nevis": "saint kitts and nevis",
            "cote divoire": "ivory coast",
            "holy see": "vatican city",
            "cabo verde": "cape verde",
        }

        updated = 0
        unmatched = []

        for db_country in Country.objects.all():
            key = _norm(db_country.name)
            if key in aliases:
                key = _norm(aliases[key])

            code = lookup.get(key)
            if not code:
                unmatched.append(db_country.name)
                continue

            if db_country.country_code != code:
                db_country.country_code = code
                db_country.save(update_fields=["country_code"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Updated countries: {updated}"))
        if unmatched:
            self.stdout.write(self.style.WARNING(f"Unmatched countries: {len(unmatched)}"))
            for name in unmatched:
                self.stdout.write(f"- {name}")
