import pytest
from django.test import TestCase

from pgr_django.utils.google_translate import GoogleTranslate
from .factories import PropertyFactory
from ..models import (
    Property,
    PropertyDescTranslation,
)
from ..constants import TRANSLATION_TRANSLATED

pytestmark = pytest.mark.django_db
