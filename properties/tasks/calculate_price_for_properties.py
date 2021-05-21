import logging

from config import celery_app
from pgr_django.properties.models import Property


logger = logging.getLogger(__name__)


@celery_app.task
def update_calculated_price_avg_for_properties():
    properties = Property.objects.filter(calculated_price_avg__isnull=True)
    for prop in properties.iterator():
        prop.calculate_and_set_price_avg()
        prop.save(update_fields=["calculated_price_avg"])
