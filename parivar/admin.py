from django.contrib import admin

from parivar.services import CSVImportService
from .models import *
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

# class PersonAdmin(admin.ModelAdmin):

#     def save_model(self, request, obj, form, change):

# if obj.date_of_birth:
#     if obj.date_of_birth.year < 1947 or obj.date_of_birth.year > datetime.datetime.now().year:
#         raise ValidationError({'date_of_birth': ["Date of birth must be between 1947 and the current year."]})
# super().save_model(request, obj, form, change)

# Register your models here.

COMMON_CONTEXT = {
    "show_save_and_continue": False,
    "show_save_and_add_another": False,
    "show_delete": False,
}

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

admin.site.register(User)

@admin.register(Surname)
class SurnameAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "samaj", "top_member", "guj_name", "fix_order"]
    list_filter = ["samaj", "samaj__village"]
    search_fields = ["name", "guj_name", "samaj__name"]

@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
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
class PersonAdmin(ImportExportModelAdmin):
    # resource_class = PersonResource
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

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        
        # Sync the guj_first_name and guj_middle_name fields into TranslatePerson
        if obj.guj_first_name or obj.guj_middle_name:
            trans_person = TranslatePerson.objects.filter(person_id=obj, language='guj').first()
            if trans_person:
                trans_person.first_name = obj.guj_first_name or ''
                trans_person.middle_name = obj.guj_middle_name or ''
                trans_person.save()
            else:
                TranslatePerson.objects.create(
                    person_id=obj,
                    language='guj',
                    first_name=obj.guj_first_name or '',
                    middle_name=obj.guj_middle_name or '',
                    address=obj.address or '',
                    out_of_address=obj.out_of_address or ''
                )

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
        # Fetch the first name from the TranslatePerson model
        translate_person = obj.translateperson.filter(language='guj').first()
        if translate_person:
            return translate_person.first_name
        return "-"

    def guj_middle_name(self, obj):
        # Fetch the first name from the TranslatePerson model
        translate_person = obj.translateperson.filter(language='guj').first()
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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-custom-csv/', self.admin_site.admin_view(self.import_custom_csv), name='import-custom-csv'),
        ]
        return custom_urls + urls

    def import_custom_csv(self, request):
        if request.method == "POST":
            csv_file = request.FILES.get("csv_file")
            is_demo = request.POST.get("is_demo") == "on"
            if not csv_file:
                self.message_user(request, "Please upload a file.", level=messages.ERROR)
                return redirect("..")
            
            result = CSVImportService.process_file(csv_file, request=request, is_demo=is_demo)
            
            if "error" in result:
                self.message_user(request, f"Error: {result['error']}", level=messages.ERROR)
            else:
                msg = f"Import successful! Created {result['created']} and updated {result['updated']} entries."
                if result.get('bug_file_url'):
                    msg += f' <a href="{result["bug_file_url"]}" target="_blank">Download Bug CSV</a>'
                self.message_user(request, mark_safe(msg), level=messages.SUCCESS)
            
            return redirect("..")
        
        context = {
            **self.admin_site.each_context(request),
            "title": "Import Custom CSV",
            "opts": self.model._meta,
        }
        return TemplateResponse(request, "admin/parivar/person/import_csv.html", context)


@admin.register(TranslatePerson)
class TranslatePersonAdmin(ImportExportModelAdmin):
    # resource_class = TranslatePersonResource
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

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "state", "guj_name"]

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "guj_name"]

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "guj_name"]

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


@admin.register(Samaj)
class SamajAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'village', 'guj_name', 'referral_code', 'is_premium', 'created_at']
    search_fields = ['name', 'guj_name', 'referral_code', 'village__name']
    list_filter = ['is_premium', 'created_at', 'village']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Village)
class VillageAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "guj_name", "get_district", "taluka", "is_active"]
    list_filter = ["taluka__district", "taluka", "is_active"]
    # readonly_fields = ["view_invitation_link"]

    def get_district(self, obj):
        return obj.taluka.district.name
    get_district.short_description = "District"

    # def view_invitation_link(self, obj):
    #     data = {
    #         "v_id": obj.id,
    #         "t_id": obj.taluka.id,
    #         "d_id": obj.taluka.district.id
    #     }
    #     token = signing.dumps(data)
    #     # Use the base URL from settings if available, otherwise fallback
    #     base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
    #     path = reverse("parivar:decode-invite-link", kwargs={"token": token})
    #     url = f"{base_url}{path}"
    #     return mark_safe(f'<a href="{url}" target="_blank">Copy Invite Link</a><br><small>{url}</small>')
    
    # view_invitation_link.short_description = "Invitation Link"

@admin.register(ParentChildRelation)
class ParentChildRelationAdmin(admin.ModelAdmin):
    list_display = ["id", "parent", "child", "created_user", "is_deleted", "is_demo"]
    list_filter = ["is_demo", "is_deleted"]
    search_fields = ["parent__first_name", "child__first_name"]

@admin.register(RandomBanner)
class RandomBannerAdmin(admin.ModelAdmin):
    list_display = ["id", "is_random_banner", "created_at", "updated_at"]

    def has_add_permission(self, request):
        if RandomBanner.objects.count() == 1:
            return False
        return True

@admin.register(PersonUpdateLog)
class PersonUpdateLogAdmin(admin.ModelAdmin):
    list_display = ["id", "person", "updated_history", "created_person", "created_at"]

    # def has_delete_permission(self, request, obj=None):
    #     return False
