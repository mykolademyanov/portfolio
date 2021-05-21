from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.contrib.sites.models import Site
from django.db import transaction
from django.utils import translation
from django.utils.functional import cached_property
from django.utils.translation import gettext, gettext_lazy
from djmoney.models.fields import MoneyField
from model_utils import FieldTracker

from pgr_django.apps_translations.models import TranslationAbstractModel
from pgr_django.properties.constants import (
    TYPE_CHOICES,
    STATUS_INACTIVE,
    STATUS_CHOICES,
    SUBTYPE_CHOICES,
    TRANSLATION_OUTDATED,
    PROPERTIES_FILE_STATUSES,
    STATUS_PENDING,
)
from pgr_django.users.models import Agent
from config.constants import LANGUAGE_CHOICES

from pgr_django.properties.constants import (
    RENT, TR_FOR_SALE_IN, TR_FOR_RENT_IN, TR_WITH_DASHES,
)


class Property(models.Model):
    property_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    property_subtype = models.CharField(max_length=50, choices=SUBTYPE_CHOICES)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_INACTIVE)
    price = MoneyField(max_digits=15, decimal_places=2, default_currency="USD", null=True, blank=True)
    price_min = MoneyField(max_digits=15, decimal_places=2, default_currency="USD", null=True, blank=True)
    price_max = MoneyField(max_digits=15, decimal_places=2, default_currency="USD", null=True, blank=True)
    calculated_price_avg = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    monthly_hoa_fee = MoneyField(
        max_digits=10, decimal_places=2, default_currency="USD", null=True, blank=True)
    monthly_hoa_fee_min = MoneyField(
        max_digits=10, decimal_places=2, default_currency="USD", null=True, blank=True)
    monthly_hoa_fee_max = MoneyField(
        max_digits=10, decimal_places=2, default_currency="USD", null=True, blank=True)
    address = models.CharField(max_length=615, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    region = models.CharField(max_length=100, blank=True, null=True)  # State in US
    city = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=15, blank=True, null=True)
    street = models.CharField(max_length=200, blank=True, null=True)
    location = models.PointField(default=Point(0, 0, srid=4326), srid=4326)
    beds = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    beds_min = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    beds_max = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    baths = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    baths_min = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    baths_max = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    size = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    lot_size = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    lot_size_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    lot_size_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    building_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    parking_space = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    build_year = models.SmallIntegerField(blank=True, null=True)
    unit = models.SmallIntegerField(blank=True, null=True)  # for condo properties
    amenities = models.TextField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    description_language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    agent = models.ForeignKey("users.Agent", on_delete=models.PROTECT, null=True, related_name="properties")
    run_token = models.CharField(max_length=64, blank=True, null=True)
    buy_rent = models.CharField(max_length=4, db_index=True)
    grm = models.DecimalField(blank=True, null=True, max_digits=10, decimal_places=2)
    cap_rate = models.DecimalField(blank=True, null=True, max_digits=12, decimal_places=3)
    website_link = models.URLField(blank=True, null=True, max_length=300)
    live_tour_link = models.URLField(blank=True, null=True, max_length=300)
    tenancy = models.IntegerField(blank=True, null=True)
    # original property_type and property_subtype, 1:1 as it was imported from scraping
    org_property_type = models.CharField(max_length=20, null=True, blank=True)
    org_property_subtype = models.CharField(max_length=20, null=True, blank=True)
    realtor_agent_id = models.IntegerField(blank=True, null=True)
    payment = models.ForeignKey("payments.Payment", on_delete=models.PROTECT, null=True, blank=True)
    paid_from = models.DateTimeField(null=True, blank=True)
    paid_to = models.DateTimeField(null=True, blank=True)
    # stripe
    subscription = models.ForeignKey("payments.Subscription", related_name='property', on_delete=models.PROTECT, null=True, blank=True)
    priority = models.SmallIntegerField(default=1)  # 1: first priority to show, 2: second priority. This field is used for sorting listings on the first stage. in the future, after we'll get more real listings we can remove this field
    free_marketing = models.BooleanField(default=False)
    #
    scraped = models.BooleanField(default=False)
    featured = models.PositiveIntegerField(null=True, blank=True)

    field_tracker = FieldTracker(
        [
            "buy_rent",
            "price", "price_min", "price_max",
            "monthly_hoa_fee", "monthly_hoa_fee_min", "monthly_hoa_fee_max"
        ]
    )

    # helpers to determine if translation need to be updated
    __initial_description = None
    __initial_description_language = None
    __initial_address = None
    __initial_full_address = None

    class Meta:
        verbose_name_plural = "Properties"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__initial_description = self.description
        self.__initial_description_language = self.description_language
        self.__initial_address = self.address
        self.__initial_full_address = self.full_address

    @property
    def needs_translation_update(self) -> bool:
        prop_fields = [
            'description', 'description_language', 'address', 'full_address'
        ]
        fields = [
            field for field in prop_fields
            if getattr(self, f"_Property__initial_{field}", None) !=
               getattr(self, field, None)
        ]

        return bool(fields)

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        # for new/prior properties there will be no corresponding translation
        # hasattr is safe and will not raise PropertyDescTranslation.DoesNotExist:
        if self.needs_translation_update and hasattr(self, 'description_translation'):
            with transaction.atomic():
                self.description_translation.translation_status = TRANSLATION_OUTDATED
                # TODO: try to cancel pending job if TRANSLATION_PROCESSING and clear job_id regardless
                self.description_translation.job_id = None
                self.description_translation.save(update_fields=['translation_status', 'job_id'])

                super().save(force_insert, force_update, *args, **kwargs)
        else:
            super().save(force_insert, force_update, *args, **kwargs)

        self.__initial_description = self.description
        self.__initial_description_language = self.description_language
        # do not auto translate .. serializer or admin form must do it manually

    @cached_property
    def full_address(self) -> str:
        address = ", ".join(str(column) for column in [
            self.country, self.region, self.city, self.district,
            self.street, self.zip_code] if column) or "Address unknown"

        return address

    @property
    def lat(self) -> float:
        if self.location:
            return self.location.x

    @property
    def lng(self) -> float:
        if self.location:
            return self.location.y

    @cached_property
    def _agent(self):
        if self.agent is None:
            return Agent.default_agent()
        return self.agent

    def __str__(self):
        return self.full_address

    def get_default_url(self) -> str:
        buy_rent = 'for-rent-in' if self.buy_rent == RENT else 'for-sale-in'
        country = self.country.replace(' ', '-')
        subtype = self.property_subtype.replace(' ', '-')
        city = self.city.replace(' ', '-').replace('/', '-')
        return f"/en/{country}/{subtype}-{buy_rent}-{city}/{self.id}"

    def get_translated_url(self, lang, prop_translation) -> str or None:
        """
        Returns translated URL if translation available,
        else returns URL in english.
        """
        buy_rent = TR_FOR_RENT_IN if self.buy_rent == RENT else TR_FOR_SALE_IN
        if lang not in prop_translation.translations.keys():
            lang = 'en'
        translation.activate(lang)
        trans_fields = {
            'buy_rent': gettext(buy_rent),
            'property_subtype': self.get_url_subtype_translation()
        }
        country = prop_translation.translations[lang].get('country')
        # remove slashes in city names to have correct URL
        city = prop_translation.translations[lang].get('city', '').replace('/', '-')
        slug = trans_fields['buy_rent']
        subtype = trans_fields['property_subtype']
        values = [country, city, slug, subtype]
        if None in values or '' in values:
            return self.get_default_url()
        country, city, slug, subtype = [v.replace(' ', '-') for v in values]
        return f"/{lang}/{country}/{subtype}-{slug}-{city}/{self.id}"

    def get_absolute_url(self):
        """Sitemap generation is heavily tied to this method."""
        lang = translation.get_language()
        prop_translation = PropertyDescTranslation.objects.filter(property=self).first()
        if prop_translation:
            url = self.get_translated_url(lang, prop_translation)
            url = url if url else self.get_default_url()
        else:
            url = self.get_default_url()
        return url

    def get_url_subtype_translation(self):
        multifamily_translation = lambda subt: f"{gettext_lazy(subt)}-{gettext_lazy('multiFamily')}"
        subtype = self.property_subtype.lower()
        types = {
            'house': 'propertyTypeHouse',
            'condo': 'propertyTypeCondo',
            'apartment': 'apartments',
            'land': 'land',
            'multi-family': 'multiFamily',
            'office': 'office',
            'other': 'other',
            'industrial': 'industrial',
            'retail': 'retail',
            'condo-multi-family': multifamily_translation('propertyTypeCondo'),
            'house-multi-family': multifamily_translation('propertyTypeHouse')
        }
        types = {
            k: gettext_lazy(v)
            for k, v in types.items() if type(v) is str
        }
        return types.get(subtype)

    def get_attr_from_prop(self):
        res = {'buy_rent': TR_FOR_SALE_IN}
        if getattr(self, 'buy_rent', '') == RENT:
            res.update({'buy_rent': TR_FOR_RENT_IN})

        res['property_subtype'] = getattr(self, 'property_subtype',
                                          '').lower()

        tr_with_dash = TR_WITH_DASHES.get(res['property_subtype'])
        if tr_with_dash:
            res['property_subtype'] = tr_with_dash

        return res

    def calculate_and_set_price_avg(self):
        if self.buy_rent == RENT:
            fixed_price = self.monthly_hoa_fee
            min_price = self.monthly_hoa_fee_min
            max_price = self.monthly_hoa_fee_max
        else:
            fixed_price = self.price
            min_price = self.price_min
            max_price = self.price_max

        if fixed_price is not None:
            self.calculated_price_avg = fixed_price.amount

        elif min_price is not None and max_price is not None:
            self.calculated_price_avg = (
                (min_price.amount + max_price.amount) / 2
            )
        else:
            self.calculated_price_avg = 0


class PropertyMediaAttachment(models.Model):
    def get_target_path(self, filename):
        path = [str(self.property.id), filename]
        return "/".join([elm for elm in path if elm])

    property = models.ForeignKey(
        "Property", on_delete=models.CASCADE
    )  # should be overridden with related_name
    # TODO: blank/null only set for migration stage
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    order = models.SmallIntegerField(null=True, blank=True)

    class Meta:
        abstract = True


class PropertyPhoto(PropertyMediaAttachment):
    def get_target_path(self, filename):
        return super().get_target_path(filename)

    photo = models.ImageField(upload_to=get_target_path)
    property = models.ForeignKey(
        "Property", on_delete=models.CASCADE, related_name="photos"
    )

    def __str__(self):
        return self.photo.name


class PropertyFile(PropertyMediaAttachment):
    def get_target_path(self, filename):
        return super().get_target_path(filename)

    file = models.FileField(upload_to=get_target_path)
    property = models.ForeignKey(
        "Property", on_delete=models.CASCADE, related_name="files"
    )

    def __str__(self):
        return self.file.name


class PropertyDescTranslation(TranslationAbstractModel):
    property = models.OneToOneField("Property", on_delete=models.CASCADE, related_name="description_translation")


class UserSavedProperty(models.Model):
    user = models.ForeignKey("users.User", related_name="saved_properties", on_delete=models.CASCADE)
    property = models.ForeignKey("Property", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # property updated_at copy
    last_updated_at = models.DateTimeField(blank=True, null=True)
    # property status copy
    last_status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'property'], name='uq_saved_property_user')
        ]


class ScrapedPropertiesFile(models.Model):
    file = models.FileField(upload_to='scraped_data/%d_%m_%Y/')
    status = models.CharField(max_length=20, choices=PROPERTIES_FILE_STATUSES, default=STATUS_PENDING)
    created = models.DateTimeField(auto_now_add=True)
    rows_uploaded = models.PositiveIntegerField(null=True, blank=True)
    rows_total = models.PositiveIntegerField(null=True, blank=True)
    error = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.file.name

