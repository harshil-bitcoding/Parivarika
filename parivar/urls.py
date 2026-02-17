from django.urls import path
from . import views
from .views import *
from .views import LoginAPI
from .v2 import views as V2Views
from .v3 import views as V3Views
from .v4 import views as V4Views

app_name = "parivar"

urlpatterns = [
    ########### V1 Version APIs History ###########
    path("", views.index, name="index"),
    path("api/v1/login", LoginAPI.as_view(), name="login"),
    path("api/v1/surname", SurnameDetailView.as_view(), name="surname_detail"),
    path("api/v1/relation", ParentChildRelationDetailView.as_view(), name="relation"),
    path(
        "api/v1/relation/<str:surnameid>",
        ParentChildRelationDetailView.as_view(),
        name="relation",
    ),
    path(
        "api/v1/get-person-by-surname",
        PersonBySurnameView.as_view(),
        name="get-person-by-surname",
    ),
    path("api/v1/bloodgroup", BloodGroupDetailView.as_view(), name="bloodgroup_detail"),
    path("api/v1/profile", ProfileDetailView.as_view(), name="profile-list"),
    path("api/v2/profile/<int:id>", ProfileDetailView.as_view(), name="profile-list"),
    path("api/v1/person", PersonDetailView.as_view(), name="person-list"),
    path(
        "api/v1/admin-person", AdminPersonDetailView.as_view(), name="admin-person-list"
    ),
    path(
        "api/v1/admin-person/<int:pk>/<int:admin_user_id>",
        AdminPersonDetailView.as_view(),
        name="admin-person-list",
    ),
    path("api/v1/person/<int:pk>", PersonDetailView.as_view(), name="person-detail"),
    path(
        "api/v1/person/pending-approve-new-member",
        PendingApproveDetailView.as_view(),
        name="pending-approve-new-member",
    ),
    path("api/v1/city/<int:state_id>", CityDetailView.as_view(), name="city_detail"),
    path("api/v1/state", StateDetailView.as_view(), name="state_detail"),
    path("api/v1/banner", BannerDetailView.as_view(), name="banner_detail"),
    path("api/v1/banner/<int:pk>", BannerDetailView.as_view(), name="banner_detail"),
    path("api/v1/country", CountryDetailView.as_view(), name="country_detail"),
    path("api/v1/admin-access", AdminAccess.as_view(), name="country_detail"),
    path("api/v1/child-person", ChildPerson.as_view(), name="child_person"),
    path("api/v2/child-person", V2Views.ChildPerson.as_view(), name="child_person_v2"),
    path("api/v1/all-admin", AdminPersons.as_view(), name="admin_person"),
    path("api/v1/relation-tree", RelationtreeAPIView.as_view(), name="relation_tree"),
    path("privacy-policy", views.privacy_policy_app, name="privacy_policy"),
    path("terms-condition", views.terms_condition_app, name="terms_condition"),
    ########### V2 Version APIs History ###########
    path("api/v2/login", V2Views.LoginAPI.as_view(), name="login"),
    path("api/v2/surname", V2Views.SurnameDetailView.as_view(), name="surname_detail"),
    path(
        "api/v2/relation",
        V2Views.ParentChildRelationDetailView.as_view(),
        name="relation",
    ),
    path(
        "api/v2/relation/<str:surnameid>",
        V2Views.ParentChildRelationDetailView.as_view(),
        name="relation",
    ),
    path(
        "api/v2/get-person-by-surname",
        V2Views.PersonBySurnameView.as_view(),
        name="get-person-by-surname",
    ),
    path(
        "api/v2/bloodgroup",
        V2Views.BloodGroupDetailView.as_view(),
        name="bloodgroup_detail",
    ),
    path(
        "api/v2/profile/<int:id>",
        V2Views.ProfileDetailView.as_view(),
        name="profile-list",
    ),
    path("api/v2/person", V2Views.PersonDetailView.as_view(), name="person-list"),
    path(
        "api/v2/admin-person",
        V2Views.AdminPersonDetailView.as_view(),
        name="admin-person-list",
    ),
    path(
        "api/v2/admin-person/<int:pk>/<int:admin_uid>",
        V2Views.AdminPersonDetailView.as_view(),
        name="admin-person-list",
    ),
    path(
        "api/v2/person/<int:pk>",
        V2Views.PersonDetailView.as_view(),
        name="person-detail",
    ),
    path(
        "api/v2/person/pending-approve-new-member",
        V2Views.PendingApproveDetailView.as_view(),
        name="pending-approve-new-member",
    ),
    path(
        "api/v2/city/<int:state_id>",
        V2Views.CityDetailView.as_view(),
        name="city_detail",
    ),
    path("api/v2/state", V2Views.StateDetailView.as_view(), name="state_detail"),
    path("api/v2/banner", V2Views.BannerDetailView.as_view(), name="banner_detail"),
    path(
        "api/v2/banner/<int:pk>",
        V2Views.BannerDetailView.as_view(),
        name="banner_detail",
    ),
    path("api/v2/country", V2Views.CountryDetailView.as_view(), name="country_detail"),
    ############## v3 Version APIs History ##########################
    path(
        "api/v3/relation",
        V3Views.ParentChildRelationDetailViewV3.as_view(),
        name="relation_list",
    ),
    path(
        "api/v3/relation/<str:surnameid>",
        V3Views.ParentChildRelationDetailViewV3.as_view(),
        name="relation",
    ),
    path(
        "api/v3/get-person-by-surname",
        V3Views.PersonBySurnameViewV3.as_view(),
        name="get-person-by-surname",
    ),
    path(
        "api/v3/middle-name-update",
        V3Views.PersonMiddleNameUpdate.as_view(),
        name="middle_name_update",
    ),
    path(
        "api/v3/search-by-person",
        V3Views.SearchbyPerson.as_view(),
        name="search_by_person",
    ),
    path("api/v3/login", V3Views.V3LoginAPI.as_view(), name="login"),
    path(
        "api/v3/additional-data",
        V3Views.AdditionalData.as_view(),
        name="additional_data",
    ),
    path("api/v3/surname", V3Views.V3SurnameDetailView.as_view(), name="surname_data"),
    path(
        "api/v3/banner", V3Views.V3BannerDetailView.as_view(), name="banner_detail_list"
    ),
    path(
        "api/v3/banner/<int:pk>",
        V3Views.V3BannerDetailView.as_view(),
        name="banner_detail",
    ),
    path(
        "api/v3/random-banner", V3Views.RandomBannerView.as_view(), name="random_banner"
    ),
    path(
        "api/v3/first-capital",
        V3Views.FirstCapitalize.as_view(),
        name="first_charecter_capitalize",
    ),

    ##############################################  version 4 APIs   ###############################################
    path(
        "api/v4/admin-person/<int:pk>/<int:admin_user_id>",
        V4Views.V4AdminPersonDetailView.as_view(),
        name="admin-person-list",
    ),

    path("api/v4/admin-access", V4Views.V4AdminAccess.as_view(), name="country_detail"),
    path("api/v4/child-person", V2Views.ChildPerson.as_view(), name="child_person_v2"),
    path("api/v4/all-admin", V4Views.V4AdminPersons.as_view(), name="admin_person"),
    path("api/v4/relation-tree", V4Views.V4RelationtreeAPIView.as_view(), name="relation_tree"),

    path(
        "api/v4/bloodgroup",
        V2Views.BloodGroupDetailView.as_view(),
        name="bloodgroup_detail",
    ),
    path(
        "api/v4/profile/<int:id>",
        V2Views.ProfileDetailView.as_view(),
        name="profile-list",
    ),
    path("api/v4/profile", ProfileDetailView.as_view(), name="profile-list"),
    path("api/v4/person", V2Views.PersonDetailView.as_view(), name="person-list"),
    path(
        "api/v4/person/<int:pk>",
        V2Views.PersonDetailView.as_view(),
        name="person-detail",
    ),
    path(
        "api/v4/person/pending-approve-new-member",
        V2Views.PendingApproveDetailView.as_view(),
        name="pending-approve-new-member",
    ),
    
    path(
        "api/v4/admin-person",
        V4Views.V4AdminPersonDetailView.as_view(),
        name="admin-person-list",
    ),

    path(
        "api/v4/admin-person/<int:pk>/<int:admin_uid>",
        V4Views.V4AdminPersonDetailView.as_view(),
        name="admin-person-list",
    ),
    path(
        "api/v4/city/<int:state_id>",
        V2Views.CityDetailView.as_view(),
        name="city_detail",
    ),
    path("api/v4/state", V2Views.StateDetailView.as_view(), name="state_detail"),

    path("api/v4/country", V2Views.CountryDetailView.as_view(), name="country_detail"),

    path(
        "api/v4/relation",
        V4Views.V4ParentChildRelationDetailView.as_view(),
        name="relation_list",
    ),
    path(
        "api/v4/relation/<str:surnameid>/<int:request_village_id>",
        V4Views.V4ParentChildRelationDetailView.as_view(),
        name="relation",
    ),

    path(
        "api/v4/surname-by-village",
        V4Views.SurnameByVillageView.as_view(),
        name="get_surname_by_village",
    ),

    path("api/v4/person", V4Views.V4PersonDetailView.as_view(), name="person_list_v4"),

    path("api/v4/person/<int:pk>", V4Views.V4PersonDetailView.as_view(), name="person_detail_v4"),

    path(
        "api/v4/get-person-by-surname",
        V3Views.PersonBySurnameViewV3.as_view(),
        name="get-person-by-surname",
    ),
    path(
        "api/v4/middle-name-update",
        V3Views.PersonMiddleNameUpdate.as_view(),
        name="middle_name_update",
    ),
    # path(
    #     "api/v4/search-by-person",
    #     V4Views.V4SearchbyPerson.as_view(),
    #     name="search_by_person",
    # ),
    path("api/v4/login", V4Views.V4LoginAPI.as_view(), name="login"),
    path(
        "api/v4/additional-data",
        V3Views.AdditionalData.as_view(),
        name="additional_data",
    ),
    path("api/v4/surname", V3Views.V3SurnameDetailView.as_view(), name="surname_data"),
    path(
        "api/v4/banner", V3Views.V3BannerDetailView.as_view(), name="banner_detail_list"
    ),
    path(
        "api/v4/banner/<int:pk>",
        V3Views.V3BannerDetailView.as_view(),
        name="banner_detail",
    ),
    path(
        "api/v4/random-banner", V3Views.RandomBannerView.as_view(), name="random_banner"
    ),
    path(
        "api/v4/first-capital",
        V3Views.FirstCapitalize.as_view(),
        name="first_charecter_capitalize",
    ),
    path(
        "api/v4/districts",
        V4Views.DistrictDetailView.as_view(),
        name="district_detail",
    ),
    path(
        "api/v4/talukas/<int:district_id>",
        V4Views.TalukaDetailView.as_view(),
        name="taluka_detail",
    ),
    path(
        "api/v4/villages/<int:taluka_id>",
        V4Views.VillageDetailView.as_view(),
        name="village_detail",
    ),
    path("api/v4/samaj", V4Views.SamajListView.as_view(), name="samaj_list_v4"),
    path("api/v4/samaj-by-village", V4Views.SamajByVillageView.as_view(), name="samaj_by_village_v4"),

]
