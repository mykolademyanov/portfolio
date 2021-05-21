import pytest
from django.urls import resolve, reverse

pytestmark = pytest.mark.django_db


def test_properties_list():
    assert (reverse("properties:list") == "/properties/list")
    assert resolve("/properties/list").view_name == "properties:list"


def test_properties_detail(pk: int = 1):
    assert reverse("properties:get", kwargs={"pk": pk}) == f"/properties/get/{pk}"
    assert resolve(f"/properties/get/{pk}").view_name == "properties:get"


def test_properties_search():
    assert reverse("properties:search") == "/properties/search"
    assert resolve("/properties/search").view_name == "properties:search"


def test_properties_types_map():
    assert reverse("properties:types-map") == "/properties/types-map/"
    assert resolve("/properties/types-map/").view_name == "properties:types-map"


def test_properties_photo_add(property_id: int = 1):
    assert reverse("properties:photo-add",
                   kwargs={"property_id": property_id}) == f"/properties/property/{property_id}/photos-upload"
    assert resolve(f"/properties/property/{property_id}/photos-upload").view_name == "properties:photo-add"


def test_properties_photo_detail(property_id: int = 1, pk: int = 1):
    assert reverse("properties:photo-detail",
                   kwargs={"property_id": property_id, 'pk': pk}) == f"/properties/property/{property_id}/photos/{pk}"
    assert resolve(f"/properties/property/{property_id}/photos/{pk}").view_name == "properties:photo-detail"


def test_properties_photo_list(property_id: int = 1):
    assert reverse("properties:photo-list",
                   kwargs={"property_id": property_id}) == f"/properties/property/{property_id}/photos"
    assert resolve(f"/properties/property/{property_id}/photos").view_name == "properties:photo-list"


def test_properties_count():
    assert reverse("properties:count") == "/properties/count"
    assert resolve(f"/properties/count").view_name == "properties:count"


def test_properties_user_saved_detail(property_id: int = 1):
    assert reverse("properties:user-saved-detail", kwargs={"property_id": property_id}) == f"/properties/user-saved/{property_id}/"
    assert resolve(f"/properties/user-saved/{property_id}/").view_name == "properties:user-saved-detail"


def test_properties_user_saved_list():
    assert reverse("properties:user-saved-list") == f"/properties/user-saved/"
    assert resolve(f"/properties/user-saved/").view_name == "properties:user-saved-list"
