import traceback

from config import celery_app
from pgr_django.properties.constants import (
    FILE_STATUS_UPLOADED,
    STATUS_UPLOADING,
    FILE_STATUS_ERROR
)
from pgr_django.properties.models import ScrapedPropertiesFile
from pgr_django.utils.properties_parser import PropertiesParser


@celery_app.task
def import_properties_from_file(object_id):
    """Import file with properties."""
    file_obj = ScrapedPropertiesFile.objects.get(id=object_id)
    if file_obj.status == STATUS_UPLOADING:
        return  # do not start task if it is still uploading
    else:
        file_obj.status = STATUS_UPLOADING
        file_obj.save()

    try:
        parser = PropertiesParser(file_obj.file.url)
        parser.populate_db()
    except Exception:
        file_obj.status = FILE_STATUS_ERROR
        file_obj.error = traceback.format_exc()
        file_obj.save()
    else:
        file_obj.status = FILE_STATUS_UPLOADED
        file_obj.rows_total = parser.rows_total
        file_obj.rows_uploaded = parser.rows_uploaded
        file_obj.save()


@celery_app.task
def update_rent_properties_from_file(object_id):
    """Import file with properties."""
    file_obj = ScrapedPropertiesFile.objects.get(id=object_id)
    if file_obj.status == STATUS_UPLOADING:
        return  # do not start task if it is still uploading
    else:
        file_obj.status = STATUS_UPLOADING
        file_obj.save()
    try:
        parser = PropertiesParser(file_obj.file.url)
        parser.update_rent_properties()
    except Exception:
        file_obj.status = FILE_STATUS_ERROR
        file_obj.error = traceback.format_exc()
        file_obj.save()
    else:
        file_obj.status = FILE_STATUS_UPLOADED
        file_obj.rows_total = parser.rows_total
        file_obj.rows_uploaded = parser.rows_uploaded
        file_obj.save()
