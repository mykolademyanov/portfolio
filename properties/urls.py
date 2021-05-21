from django.urls import path

from .views import (
    property_photo_detail_get_delete_view,
    property_photo_detail_patch_view,
    property_photo_list_view,
    property_photo_upload_view,
    properties_count_view,
    properties_create_view,
    properties_detail_view,
    properties_list_view,
    properties_partial_update_view,
    properties_search_view,
    properties_search_my_properties_view,
    properties_type_subtype_get_view,
    properties_update_view,
    user_saved_properties_detail,
    user_saved_properties_list,
    property_file_upload_view,
    property_file_detail_get_delete_view,
    property_file_list_view,
    property_file_detail_patch_view,
    properties_file_upload_view,
    properties_file_update_rent_view,
    featured_properties_list_view,
    properties_address_search_view,
    properties_area_search,
    property_low_detailed_view,
)

app_name = "properties"

urlpatterns = [
    path("search", view=properties_search_view, name="search"),
    path("my-properties", view=properties_search_my_properties_view, name="my-properties"),
    path("list", view=properties_list_view, name="list"),
    path("get/<pk>", view=properties_detail_view, name="get"),

    path("create", view=properties_create_view, name="create"),
    path("count", view=properties_count_view, name="count"),
    path("update/<pk>", view=properties_update_view, name="update"),
    path("patch/<pk>", view=properties_partial_update_view, name="patch"),

    path("types-map/", view=properties_type_subtype_get_view, name="types-map"),

    path("property/<int:property_id>/photos-upload", view=property_photo_upload_view, name="photo-add"),
    path("property/<int:property_id>/photos", view=property_photo_list_view, name="photo-list"),
    path("property/<int:property_id>/photos/<int:pk>", view=property_photo_detail_get_delete_view, name="photo-detail"),
    path("property/<int:property_id>/photos/<int:pk>/patch", view=property_photo_detail_patch_view, name="photo-detail-patch"),

    path("property/<int:property_id>/files-upload", view=property_file_upload_view, name="file-add"),
    path("property/<int:property_id>/files", view=property_file_list_view, name="file-list"),
    path("property/<int:property_id>/files/<int:pk>", view=property_file_detail_get_delete_view, name="file-detail"),
    path("property/<int:property_id>/files/<int:pk>/patch", view=property_file_detail_patch_view, name="file-detail-patch"),

    path("user-saved/", view=user_saved_properties_list, name="user-saved-list"),
    path("user-saved/<int:property_id>/", view=user_saved_properties_detail, name="user-saved-detail"),

    path("upload/", view=properties_file_upload_view, name="properties-upload"),
    path("upload-rent/", view=properties_file_update_rent_view, name="properties-upload"),

    path("featured-properties/", view=featured_properties_list_view, name="featured-properties"),
    path("properties-search/", view=properties_address_search_view, name="properties-search"),
    path("properties-area-search/", view=properties_area_search, name="properties-area-search"),
    path("property-low-detailed/<int:pk>", view=property_low_detailed_view, name="property-low-detailed"),
]
