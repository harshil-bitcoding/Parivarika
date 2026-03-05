import time
import urllib.parse
import urllib.request
import json

from django.core.management.base import BaseCommand
from django.db.models import Q

from parivar.models import Country


class Command(BaseCommand):
    help = "Fill Gujarati names (guj_name) for countries using online translation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Update Gujarati name for all countries, not only empty ones.",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.2,
            help="Delay between API calls in seconds (default: 0.2).",
        )

    def _translate_to_gujarati(self, text: str) -> str:
        # Public Google translate endpoint (no key) for simple text translation.
        query = urllib.parse.urlencode(
            {
                "client": "gtx",
                "sl": "en",
                "tl": "gu",
                "dt": "t",
                "q": text,
            }
        )
        url = f"https://translate.googleapis.com/translate_a/single?{query}"

        with urllib.request.urlopen(url, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))

        translated = "".join(part[0] for part in data[0] if part and part[0])
        return translated.strip()

    def handle(self, *args, **options):
        force = options["force"]
        pause = options["sleep"]

        qs = Country.objects.all().order_by("id")
        if not force:
            qs = qs.filter(Q(guj_name__isnull=True) | Q(guj_name=""))

        updated = 0
        failed = 0

        for country in qs:
            name = (country.name or "").strip()
            if not name:
                continue

            try:
                translated = self._translate_to_gujarati(name)
                if translated:
                    country.guj_name = translated
                    country.save(update_fields=["guj_name"])
                    updated += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

            if pause > 0:
                time.sleep(pause)

        self.stdout.write(self.style.SUCCESS(f"Updated Gujarati names: {updated}"))
        if failed:
            self.stdout.write(self.style.WARNING(f"Failed translations: {failed}"))
