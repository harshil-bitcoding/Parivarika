from django.contrib import admin
from django.db import models

from parivar.services import CSVImportService
from .models import (
    User, Surname, BloodGroup, State, City, Country,
    District, Taluka, Village, Samaj, Person, TranslatePerson,
    ParentChildRelation, AdsSetting, Banner, RandomBanner, PersonUpdateLog,
)
from django.core.exceptions import ValidationError
from .forms import PersonForm
from django_json_widget.widgets import JSONEditorWidget
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from django.utils.safestring import mark_safe
from django.template.response import TemplateResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import path


# ─────────────────────────────────────────────────────────────────────────────
#  UTILITY: Sync Person.is_admin → User.is_staff
#  Call this whenever Person.is_admin changes so the Django Admin login works.
# ─────────────────────────────────────────────────────────────────────────────

def sync_admin_staff_status(person: Person) -> None:
    """
    Bridges the Person.is_admin flag to Django's User.is_staff so that
    admins flagged on the Person model can log into the Django Admin panel
    using their Django User account.

    Usage:
        Call after saving a Person whose is_admin flag has changed.
        You can hook this into a signal or call it explicitly.

    How it works:
        - Looks up the Django User by matching mobile_number1 on both models.
        - If a matching User is found, sets is_staff=person.is_admin and saves.
        - Superusers are never demoted by this function.
    """
    if not person.mobile_number1:
        return

    try:
        user = User.objects.get(mobile_number1=person.mobile_number1)
    except User.DoesNotExist:
        return

    # Never demote a superuser
    if user.is_superuser:
        return

    if user.is_staff != person.is_admin:
        user.is_staff = person.is_admin
        user.save(update_fields=["is_staff"])


# ─────────────────────────────────────────────────────────────────────────────
#  MIXIN: SamajScopedAdmin
#  Apply this mixin to any ModelAdmin class that should be tenant-scoped.
#  Superusers always bypass scoping and see all data.
# ─────────────────────────────────────────────────────────────────────────────

class SamajScopedAdmin(admin.ModelAdmin):
    """
    Reusable mixin that enforces multi-tenant data isolation per Samaj.

    Rules:
      • Superusers → see all data (no restriction).
      • Staff (Person.is_admin) → see only data belonging to their Samaj.

    Subclasses MUST define `samaj_field` to point to the DB lookup path
    from the model to its Samaj FK, e.g.:
        samaj_field = "samaj"          # Person.samaj
        samaj_field = "samaj__id"      # same
        samaj_field = "person__samaj"  # for related models like ParentChildRelation

    For models that do not directly hold samaj (e.g., Surname), override
    `samaj_field` accordingly.
    """

    # Subclasses override this to specify the path to samaj for queryset filtering
    samaj_field: str = "samaj"

    # ── Internal helper ──────────────────────────────────────────────────────

    def _get_admin_samaj(self, request):
        """
        Returns the Samaj object for the currently logged-in admin user.
        Returns None for superusers (meaning 'no restriction').
        Returns None if no matching Person/samaj is found (treated as restricted).
        """
        if request.user.is_superuser:
            return None  # No restriction for superusers

        # Try to find the corresponding Person record for this Django User
        try:
            person = Person.objects.select_related("samaj").get(
                mobile_number1=request.user.mobile_number1,
                is_admin=True,
                is_deleted=False,
            )
            return person.samaj
        except (Person.DoesNotExist, Person.MultipleObjectsReturned):
            return None

    # ── Queryset Scoping ─────────────────────────────────────────────────────

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_superuser:
            return qs

        samaj = self._get_admin_samaj(request)
        if samaj is None:
            # Restricted admin with no Samaj resolved → return empty queryset
            return qs.none()

        # Apply scoping via the defined samaj_field path
        return qs.filter(**{self.samaj_field: samaj})

    # ── FK Dropdown Restriction ──────────────────────────────────────────────

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Restrict all ForeignKey dropdown choices to the admin's own Samaj.
        Superusers see all options unfiltered.
        """
        if not request.user.is_superuser:
            samaj = self._get_admin_samaj(request)

            if samaj is not None:
                # Scope Person / Surname / Samaj dropdowns
                if db_field.related_model == Person:
                    kwargs["queryset"] = Person.objects.filter(
                        samaj=samaj, is_deleted=False
                    )
                elif db_field.related_model == Surname:
                    kwargs["queryset"] = Surname.objects.filter(samaj=samaj)
                elif db_field.related_model == Samaj:
                    kwargs["queryset"] = Samaj.objects.filter(pk=samaj.pk)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # ── Auto-assign Samaj on Save ────────────────────────────────────────────

    def save_model(self, request, obj, form, change):
        """
        If the model being saved has a `samaj` field and the admin is
        non-superuser, forcibly assign the admin's Samaj before saving.
        This prevents orphaned records or cross-tenant data leakage.
        """
        if not request.user.is_superuser:
            samaj = self._get_admin_samaj(request)
            if samaj is not None and hasattr(obj, "samaj_id"):
                obj.samaj = samaj

        super().save_model(request, obj, form, change)

    # ── Permission overrides ─────────────────────────────────────────────────
    # Django admin requires explicit model permissions for non-superusers.
    # A samaj-scoped staff user (Person.is_admin=True) should automatically
    # get full CRUD access to models registered under SamajScopedAdmin,
    # filtered to their own Samaj via get_queryset.

    def _is_samaj_admin(self, request):
        """Returns True if the requesting user is a valid samaj-scoped admin."""
        if request.user.is_superuser:
            return True
        if not request.user.is_staff:
            return False
        try:
            return Person.objects.filter(
                mobile_number1=request.user.mobile_number1,
                is_admin=True,
                is_deleted=False,
            ).exists()
        except Exception:
            return False

    def has_module_perms(self, request):
        return self._is_samaj_admin(request) or super().has_module_perms(request)

    def has_view_permission(self, request, obj=None):
        return self._is_samaj_admin(request) or super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return self._is_samaj_admin(request) or super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return self._is_samaj_admin(request) or super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._is_samaj_admin(request) or super().has_delete_permission(request, obj)

    # ── UI: Show Samaj badge in the header area ──────────────────────────────

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        samaj = self._get_admin_samaj(request)
        if samaj:
            extra_context["samaj_scope_label"] = f"Showing data for: {samaj.name}"
        return super().changelist_view(request, extra_context=extra_context)


# ─────────────────────────────────────────────────────────────────────────────
#  COMMON CONTEXT (used by some forms to suppress extra buttons)
# ─────────────────────────────────────────────────────────────────────────────

COMMON_CONTEXT = {
    "show_save_and_continue": False,
    "show_save_and_add_another": False,
    "show_delete": False,
}


# ─────────────────────────────────────────────────────────────────────────────
#  AdsSetting Admin
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(AdsSetting)
class AdsSettingAdmin(admin.ModelAdmin):
    formfield_overrides = {models.JSONField: {"widget": JSONEditorWidget}}
    list_display = ["id", "app_title"]

    def has_add_permission(self, request):
        if AdsSetting.objects.count() == 1:
            return False
        return True

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        context.update(COMMON_CONTEXT)
        return super().render_change_form(request, context, add, change, form_url, obj)


# ─────────────────────────────────────────────────────────────────────────────
#  User Admin
# ─────────────────────────────────────────────────────────────────────────────

admin.site.register(User)


# ─────────────────────────────────────────────────────────────────────────────
#  Surname Admin  (scoped: non-superusers see only their Samaj's surnames)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Surname)
class SurnameAdmin(SamajScopedAdmin):
    samaj_field = "samaj"  # Surname.samaj

    list_display = ["id", "name", "samaj", "top_member", "guj_name", "fix_order"]
    list_filter = [("samaj", admin.RelatedOnlyFieldListFilter), "samaj__village"]
    search_fields = ["name", "guj_name", "samaj__name"]

    def get_list_filter(self, request):
        filters = list(super().get_list_filter(request))
        if request.user.is_superuser:
            return filters

        # Samaj-scoped admins: keep samaj filter, hide location-level filters.
        return [
            item
            for item in filters
            if not (isinstance(item, str) and any(t in item for t in ("village", "taluka", "district")))
        ]


# ─────────────────────────────────────────────────────────────────────────────
#  Banner Admin  (scoped via created_person → samaj)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Banner)
class BannerAdmin(SamajScopedAdmin):
    # Banners link to a Person (created_person) who belongs to a Samaj.
    # We restrict via the created_person's samaj.
    samaj_field = "created_person__samaj"

    list_display = [
        "id",
        "redirect_url",
        "created_person",
        "created_date",
        "expire_date",
        "is_active",
        "is_ad_lable",
        "is_deleted",
    ]


admin.site.register(BloodGroup)


# ─────────────────────────────────────────────────────────────────────────────
#  Person Admin  (scoped: non-superusers see only their Samaj)
# ─────────────────────────────────────────────────────────────────────────────

class TranslatePersonInline(admin.StackedInline):
    model = TranslatePerson
    extra = 0
    fields = ["first_name", "middle_name", "address", "out_of_address", "language"]


class PersonResource(resources.ModelResource):
    surname = fields.Field(
        column_name="surname",
        attribute="surname",
        widget=ForeignKeyWidget(Surname, "name"),
    )

    class Meta:
        model = Person
        fields = (
            "id",
            "first_name",
            "middle_name",
            "surname",
            "date_of_birth",
            "mobile_number1",
            "mobile_number2",
            "address",
            "out_of_address",
            "out_of_mobile",
            "out_of_country",
            "child_flag",
            "profile",
            "thumb_profile",
            "status",
            "is_same_as_father_address",
            "is_same_as_son_address",
            "password",
            "platform",
            "is_deleted",
            "is_registered_directly",
            "blood_group",
            "city",
            "state",
            "out_of_country",
            "created_time",
        )
        export_order = fields


class TranslatePersonResource(resources.ModelResource):
    person_id = fields.Field(
        column_name="person_id",
        attribute="person_id",
        widget=ForeignKeyWidget(Person, "id"),
    )
    surname = fields.Field(
        column_name="surname",
        attribute="person_id__surname",
        widget=ForeignKeyWidget(Surname, "guj_name"),
    )
    date_of_birth = fields.Field(
        column_name="date_of_birth", attribute="person_id__date_of_birth"
    )
    mobile_number1 = fields.Field(
        column_name="mobile_number1", attribute="person_id__mobile_number1"
    )
    mobile_number2 = fields.Field(
        column_name="mobile_number2", attribute="person_id__mobile_number2"
    )
    address = fields.Field(column_name="address", attribute="address")
    out_of_address = fields.Field(
        column_name="out_of_address", attribute="out_of_address"
    )
    profile = fields.Field(column_name="profile", attribute="person_id__profile")
    thumb_profile = fields.Field(
        column_name="thumb_profile", attribute="person_id__thumb_profile"
    )

    class Meta:
        model = TranslatePerson
        fields = (
            "person_id",
            "first_name",
            "middle_name",
            "surname",
            "date_of_birth",
            "mobile_number1",
            "mobile_number2",
            "address",
            "out_of_address",
            "out_of_mobile",
            "out_of_country",
            "child_flag",
            "profile",
            "thumb_profile",
            "status",
            "is_same_as_father_address",
            "is_same_as_son_address",
            "password",
            "platform",
            "is_deleted",
            "is_registered_directly",
            "blood_group",
            "city",
            "state",
            "out_of_country",
            "language",
            "created_time",
        )
        export_order = fields


@admin.register(Person)
class PersonAdmin(SamajScopedAdmin, ImportExportModelAdmin):
    samaj_field = "samaj"  # Person.samaj

    change_list_template = "admin/parivar/person/change_list.html"
    form = PersonForm
    list_display = [
        "id",
        "first_name",
        "guj_first_name",
        "middle_name",
        "guj_middle_name",
        "surname",
        "get_samaj_name",
        "get_village_full",
        "formatted_date_of_birth",
        "mobile_number1",
        "mobile_number2",
        "flag_show_billaparivar",
        "is_admin",
        "is_super_admin",
        "out_of_country_flag",
        "platform",
        "is_show_old_contact",
        "created_time",
        "is_deleted",
        "is_demo",
    ]
    search_fields = [
        "id",
        "first_name",
        "middle_name",
        "mobile_number1",
        "surname__name",
        "translateperson__first_name",
        "translateperson__middle_name",
    ]
    readonly_fields = ["deleted_at"]
    list_per_page = 100
    list_filter = [
        "is_admin",
        "flag_show",
        "is_super_admin",
        "surname",
        "is_deleted",
        "is_show_old_contact",
        "samaj",
        "samaj__village",
        "is_demo",
    ]
    inlines = [TranslatePersonInline]

    def has_import_permission(self, request):
        """Disable the default django-import-export IMPORT button for Person."""
        return False

    def get_list_filter(self, request):
        """
        Superusers keep the full filter set.
        Samaj-scoped admins get only tenant-safe filters (no role/location filters).
        """
        filters = list(super().get_list_filter(request))

        if request.user.is_superuser:
            return filters

        filtered = []
        for item in filters:
            if not isinstance(item, str):
                filtered.append(item)
                continue

            if item == "is_admin":
                continue

            if item == "is_demo":
                continue

            if any(token in item for token in ("village", "taluka", "district")):
                continue

            if item == "samaj":
                continue

            filtered.append(item)

        return filtered

    def save_model(self, request, obj, form, change):
        """
        On save: call parent SamajScopedAdmin.save_model (auto-assigns samaj),
        then sync Gujarati names into TranslatePerson,
        then sync is_admin → User.is_staff via the bridge utility.
        """
        super().save_model(request, obj, form, change)

        # Sync Gujarati names to TranslatePerson
        if obj.guj_first_name or obj.guj_middle_name:
            trans_person = TranslatePerson.objects.filter(
                person_id=obj, language="guj"
            ).first()
            if trans_person:
                trans_person.first_name = obj.guj_first_name or ""
                trans_person.middle_name = obj.guj_middle_name or ""
                trans_person.save()
            else:
                TranslatePerson.objects.create(
                    person_id=obj,
                    language="guj",
                    first_name=obj.guj_first_name or "",
                    middle_name=obj.guj_middle_name or "",
                    address=obj.address or "",
                    out_of_address=obj.out_of_address or "",
                )

        # Bridge: sync is_admin to Django User.is_staff
        sync_admin_staff_status(obj)

    # ── Display helpers ──────────────────────────────────────────────────────

    def flag_show_billaparivar(self, obj):
        return obj.flag_show

    flag_show_billaparivar.boolean = True
    flag_show_billaparivar.short_description = "Person_flag"

    def out_of_country_flag(self, obj):
        india_country_id = 1
        return obj.out_of_country.id != india_country_id

    out_of_country_flag.boolean = True
    out_of_country_flag.short_description = "Country Flag"

    def formatted_date_of_birth(self, obj):
        return str(obj.date_of_birth)[:10]

    formatted_date_of_birth.short_description = "Date of Birth"

    def guj_first_name(self, obj):
        translate_person = obj.translateperson.filter(language="guj").first()
        if translate_person:
            return translate_person.first_name
        return "-"

    def guj_middle_name(self, obj):
        translate_person = obj.translateperson.filter(language="guj").first()
        if translate_person:
            return translate_person.middle_name
        return "-"

    def get_samaj_name(self, obj):
        if obj.samaj:
            return obj.samaj.name
        return "-"

    get_samaj_name.short_description = "Samaj"

    def get_village_full(self, obj):
        if obj.samaj and obj.samaj.village:
            village = obj.samaj.village
            taluka = village.taluka.name
            district = (
                village.taluka.district.name
                if village.taluka and village.taluka.district
                else ""
            )
            return f"{village.name}, ({taluka} - {district})"
        return "-"

    get_village_full.short_description = "Village"

    # ── Custom CSV Import URL ────────────────────────────────────────────────

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-custom-csv/",
                self.admin_site.admin_view(self.import_custom_csv),
                name="import-custom-csv",
            ),
        ]
        return custom_urls + urls

    def import_custom_csv(self, request):
        if request.method == "POST":
            csv_file = request.FILES.get("csv_file")
            is_demo = request.POST.get("is_demo") == "on"
            if not csv_file:
                self.message_user(
                    request, "Please upload a file.", level=messages.ERROR
                )
                return redirect("..")

            result = CSVImportService.process_file(
                csv_file, request=request, is_demo=is_demo
            )

            if "error" in result:
                self.message_user(
                    request, f"Error: {result['error']}", level=messages.ERROR
                )
            else:
                msg = f"Import successful! Created {result['created']} and updated {result['updated']} entries."
                if result.get("bug_file_url"):
                    msg += f' <a href="{result["bug_file_url"]}" target="_blank">Download Bug CSV</a>'
                self.message_user(request, mark_safe(msg), level=messages.SUCCESS)

            return redirect("..")

        context = {
            **self.admin_site.each_context(request),
            "title": "Import Custom CSV",
            "opts": self.model._meta,
        }
        return TemplateResponse(
            request, "admin/parivar/person/import_csv.html", context
        )


# ─────────────────────────────────────────────────────────────────────────────
#  TranslatePerson Admin  (scoped via person_id → samaj)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(TranslatePerson)
class TranslatePersonAdmin(SamajScopedAdmin, ImportExportModelAdmin):
    samaj_field = "person_id__samaj"  # TranslatePerson → Person → Samaj

    list_display = [
        "id",
        "person_id",
        "first_name",
        "middle_name",
        "address",
        "out_of_address",
        "language",
    ]
    search_fields = [
        "id",
        "person_id__first_name",
        "first_name",
        "middle_name",
        "language",
    ]

    def get_export_resource_class(self):
        return TranslatePersonResource


# ─────────────────────────────────────────────────────────────────────────────
#  Location Admins  (no samaj scoping — read-only reference data)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "state", "guj_name"]


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "guj_name"]


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "guj_name", "country_code", "mobile_number_length"]


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "guj_name", "is_active"]
    list_filter = ["name"]
    search_fields = ["name", "guj_name"]


@admin.register(Taluka)
class TalukaAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "guj_name", "district", "is_active"]
    list_filter = ["district"]
    search_fields = ["name", "guj_name"]


# ─────────────────────────────────────────────────────────────────────────────
#  Samaj Admin  (superuser only — non-superusers can view but not add/delete)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Samaj)
class SamajAdmin(admin.ModelAdmin):
    list_display = [
        "id", "name", "village", "guj_name", "referral_code", "is_premium", "created_at"
    ]
    search_fields = ["name", "guj_name", "referral_code", "village__name"]
    list_filter = ["is_premium", "created_at", "village"]
    readonly_fields = ["created_at", "updated_at"]

    def get_list_filter(self, request):
        filters = list(super().get_list_filter(request))
        if request.user.is_superuser:
            return filters

        # Scoped admins should not get location hierarchy filters.
        return [
            item
            for item in filters
            if not (isinstance(item, str) and any(t in item for t in ("village", "taluka", "district")))
        ]

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Non-superusers can only see their own samaj
        try:
            person = Person.objects.get(
                mobile_number1=request.user.mobile_number1,
                is_admin=True,
                is_deleted=False,
            )
            if person.samaj:
                return qs.filter(pk=person.samaj.pk)
        except Person.DoesNotExist:
            pass
        return qs.none()


# ─────────────────────────────────────────────────────────────────────────────
#  Village Admin  (superuser only for edits)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Village)
class VillageAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "guj_name", "get_district", "taluka", "is_active"]
    list_filter = ["taluka__district", "taluka", "is_active"]

    def get_district(self, obj):
        return obj.taluka.district.name

    get_district.short_description = "District"


# ─────────────────────────────────────────────────────────────────────────────
#  ParentChildRelation Admin  (scoped via parent → samaj)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(ParentChildRelation)
class ParentChildRelationAdmin(SamajScopedAdmin):
    samaj_field = "parent__samaj"

    list_display = ["id", "parent", "child", "created_user", "is_deleted", "is_demo"]
    list_filter = ["is_demo", "is_deleted"]
    search_fields = ["parent__first_name", "child__first_name"]


# ─────────────────────────────────────────────────────────────────────────────
#  RandomBanner Admin  (scoped via samaj FK)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(RandomBanner)
class RandomBannerAdmin(SamajScopedAdmin):
    samaj_field = "samaj"

    list_display = ["id", "samaj", "is_random_banner", "created_at", "updated_at"]


# ─────────────────────────────────────────────────────────────────────────────
#  PersonUpdateLog Admin  (scoped via person → samaj)
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(PersonUpdateLog)
class PersonUpdateLogAdmin(SamajScopedAdmin):
    samaj_field = "person__samaj"

    list_display = ["id", "person", "updated_history", "created_person", "created_at"]

    # ── Superuser-only visibility ────────────────────────────────────────────
    def has_module_perms(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
