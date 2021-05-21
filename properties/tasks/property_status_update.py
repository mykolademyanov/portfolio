import logging

from config import celery_app
from pgr_django.payments.constants import ITEM_STATUS_INACTIVE
from pgr_django.properties.constants import STATUS_ACTIVE, STATUS_INACTIVE
from pgr_django.properties.models import Property


logger = logging.getLogger(__name__)


@celery_app.task
def update_expired_properties_status():
    expired_properties = Property.objects.filter(
        scraped=False,
        status=STATUS_ACTIVE,
        subscription__isnull=False,
        subscription__item_status=ITEM_STATUS_INACTIVE
    )

    logger.info("Disabling %s expired properties.", expired_properties.count())

    expired_properties.update(status=STATUS_INACTIVE)
