from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver
from pgr_django.properties.models import Property
from pgr_django.payments.constants import ITEM_STATUS_ACTIVE
from pgr_django.utils.stripe import Stripe


@receiver(pre_delete, sender=Property, dispatch_uid='property_delete_signal')
def cancel_property_subscription(sender, instance, using, **kwargs):
    subscription = instance.subscription
    if subscription and subscription.item_status == ITEM_STATUS_ACTIVE:
        stripe = Stripe()
        stripe.deactivate_property_subscription(instance)


@receiver(pre_save, sender=Property, dispatch_uid='property_price_avg_calc')
def calculate_property_price_avg(sender, instance, using, **kwargs):
    if instance.field_tracker.changed():
        instance.calculate_and_set_price_avg()
