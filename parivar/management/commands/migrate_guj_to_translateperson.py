from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from parivar.models import Person, TranslatePerson


class Command(BaseCommand):
    help = (
        "Migrate Person.guj_first_name / Person.guj_middle_name into "
        "TranslatePerson(language='guj') records."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without writing to the database.",
        )
        parser.add_argument(
            "--include-deleted",
            action="store_true",
            help="Include soft-deleted persons (is_deleted=True).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        include_deleted = options["include_deleted"]

        persons_qs = Person.objects.filter(
            Q(guj_first_name__isnull=False) | Q(guj_middle_name__isnull=False)
        ).exclude(
            Q(guj_first_name="") & Q(guj_middle_name="")
        )

        if not include_deleted:
            persons_qs = persons_qs.filter(is_deleted=False)

        persons_qs = persons_qs.order_by("id")

        created_count = 0
        updated_count = 0
        skipped_count = 0
        duplicate_warn_count = 0

        action_label = "DRY-RUN" if dry_run else "EXECUTE"
        self.stdout.write(
            self.style.WARNING(
                f"[{action_label}] Processing {persons_qs.count()} person records..."
            )
        )

        with transaction.atomic():
            for person in persons_qs.iterator(chunk_size=500):
                guj_first = (person.guj_first_name or "").strip()
                guj_middle = (person.guj_middle_name or "").strip()

                if not guj_first and not guj_middle:
                    skipped_count += 1
                    continue

                existing_qs = TranslatePerson.objects.filter(
                    person_id=person,
                    language="guj",
                    is_deleted=False,
                ).order_by("id")

                target = existing_qs.first()

                if existing_qs.count() > 1:
                    duplicate_warn_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Person {person.id}: multiple active guj translations found; "
                            f"updating oldest id={target.id}."
                        )
                    )

                if target is None:
                    if not dry_run:
                        TranslatePerson.objects.create(
                            person_id=person,
                            first_name=guj_first,
                            middle_name=guj_middle,
                            address=person.address or "",
                            out_of_address=person.out_of_address or "",
                            language="guj",
                            is_deleted=False,
                        )
                    created_count += 1
                    continue

                new_first = guj_first or (target.first_name or "")
                new_middle = guj_middle or (target.middle_name or "")

                changed = (
                    (target.first_name or "") != new_first
                    or (target.middle_name or "") != new_middle
                )

                if not changed:
                    skipped_count += 1
                    continue

                if not dry_run:
                    target.first_name = new_first
                    target.middle_name = new_middle
                    target.save(update_fields=["first_name", "middle_name"])
                updated_count += 1

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("Migration summary"))
        self.stdout.write(f"Created: {created_count}")
        self.stdout.write(f"Updated: {updated_count}")
        self.stdout.write(f"Skipped: {skipped_count}")
        self.stdout.write(f"Duplicate warnings: {duplicate_warn_count}")
        self.stdout.write(
            "Parent-child relations are unchanged by this command (read/write only on TranslatePerson)."
        )
