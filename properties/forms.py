from django import forms
from django.core.validators import validate_image_file_extension

from pgr_django.properties.models import (
    Property,
    PropertyPhoto
)


class PropertyForm(forms.ModelForm):

    photos = forms.FileField(
        widget=forms.ClearableFileInput(attrs={"multiple": True}),
        label="Photos",
        required=False,
    )

    def clean_photos(self):
        for upload in self.files.getlist("photos"):
            validate_image_file_extension(upload)

    def save_photos(self, _property):
        for upload in self.files.getlist("photos"):
            photo = PropertyPhoto(property=_property, photo=upload)
            photo.save()

    class Meta:
        model = Property
        exclude = ["created_at", "updated_at"]
