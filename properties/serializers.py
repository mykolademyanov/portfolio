from django.contrib.gis.geos import Point
from rest_framework import serializers
from rest_framework.generics import get_object_or_404
from pgr_django.payments.serializers import PaymentReadOnlySerializer, SubscriptionReadOnlySerializer
from .models import (
    Property,
    PropertyPhoto,
    PropertyFile,
    PropertyDescTranslation,
    UserSavedProperty,
    ScrapedPropertiesFile,
)
from .tasks import import_properties_from_file, update_rent_properties_from_file
from ..users.serializers import AgentDescTranslationSerializer
from ..utils.google_geocoding import GoogleGeocoding
from ..utils.get_rosseta_translations import get_translation_in
from ..utils.google_translate import GoogleTranslate
from pgr_django.properties.constants import (
    RENT, TR_FOR_SALE_IN, TR_FOR_RENT_IN, TR_WITH_DASHES,
    TR_DEFAULT_DESCRIPTION,
)
from .constants import STATUS_ACTIVE, TYPE_RESIDENTIAL


DEFAULT_LANGUAGES = "English"
SOURCE_LANGUAGE = 'en'
NEW_LANGUAGES = ['ko', 'fr']


class PointFieldSerializer(serializers.Field):
    def to_representation(self, value):
        return {
            'lat': value.x,
            'lng': value.y,
        }

    def to_internal_value(self, data):
        try:
            x = float(data.get('lat'))
        except (AttributeError, TypeError):
            raise serializers.ValidationError({'lat': 'missing or invalid latitude'})
        try:
            y = float(data.get('lng'))
        except (AttributeError, TypeError):
            raise serializers.ValidationError({'lng': 'missing or invalid longitude'})

        # TODO: temporary disable due reversed lat/lon coordinates
        # if not (-180 <= y <= 180):
        #     raise ValueError("lng out of range")
        # if not (-90 <= x <= 90):
        #     raise ValueError("lat out of range")

        return Point(x, y, srid=4326)


class MoneyFieldSerializer(serializers.Field):
    def to_representation(self, value):
        return f'{int(value.amount)} {value.currency.code}' if value else None


class BrokerSearchSerializer(serializers.Serializer):
    """minimal broker serializer for search endpoint with smaller set of fields"""
    id = serializers.IntegerField()
    owner_name = serializers.CharField()


class AgentSearchSerializer(serializers.Serializer):
    """minimal agent serializer for search endpoint with smaller set of fields"""
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    rating_avg = serializers.FloatField()
    is_active = serializers.SerializerMethodField()
    broker = BrokerSearchSerializer()  # override for minimal broker info required for search endpoint
    languages = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    additional_photo = serializers.SerializerMethodField()
    additional_photo_two = serializers.SerializerMethodField()
    description = serializers.CharField()
    description_translation = serializers.SerializerMethodField()

    @staticmethod
    def get_description_translation(obj):
        # Creates AgentDescTranslation
        if not hasattr(obj, 'description_translation'):
            prop_translation = GoogleTranslate(obj)
            prop_translation.save_translation()
        return AgentDescTranslationSerializer(obj.description_translation).data

    def get_is_active(self, obj):
        if obj.user:
            return obj.user.is_active
        return False

    @staticmethod
    def get_languages(obj):
        if obj.user and getattr(obj.user, 'languages', None):
            return obj.user.languages
        return DEFAULT_LANGUAGES

    @staticmethod
    def get_photo(obj):
        if obj.photo:
            return obj.photo.url

    @staticmethod
    def get_additional_photo(obj):
        if obj.additional_photo:
            return obj.additional_photo.url

    @staticmethod
    def get_additional_photo_two(obj):
        if obj.additional_photo_two:
            return obj.additional_photo_two.url


class AgentPropertiesSerializer(AgentSearchSerializer):
    """additional data for property listing that includes limited agent data listing"""
    email = serializers.CharField()
    phone = serializers.CharField()  # ex. office
    mobile = serializers.CharField()  # ex. cell
    fax = serializers.CharField()


class PropertyDescTranslationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyDescTranslation
        fields = ["translation_status", "translations"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['translations'] = self.update_trans_with_rosseta(
            data.get('translations'), instance.property
        )
        return data

    def update_trans_with_rosseta(
        self, translations: dict, prop_obj: Property
    ) -> dict:
        fields_vals = self.get_attr_from_prop(prop_obj)
        if 'he' not in translations:
            translations['he'] = translations.pop('iw')

        if not set(NEW_LANGUAGES).issubset(set(translations)):
            new_langs_trans = self.update_new_languages(
                prop_obj, translations['en']
            )
            self.update_desc_translations(new_langs_trans)
            translations.update(new_langs_trans)

        for lang in translations:
            trans_fields = {
                field: get_translation_in(val, lang)
                for field, val in fields_vals.items()
            }
            trans_fields.update({
                'prop_site_desc': get_translation_in(
                    'propertySiteDescription', lang
                )
            })
            trans_fields = self.set_default_description(
                prop_obj, lang, trans_fields
            )
            # Update fields with default values
            for field in ['city', 'region', 'country']:
                if field not in translations[lang].keys():
                    trans_fields[field] = getattr(prop_obj, field, '')

            translations[lang].update(trans_fields)

        return translations

    @staticmethod
    def get_attr_from_prop(prop_obj: Property):
        res = {'buy_rent': TR_FOR_SALE_IN}
        if getattr(prop_obj, 'buy_rent', '') == RENT:
            res.update({'buy_rent': TR_FOR_RENT_IN})

        res['property_subtype'] = getattr(prop_obj, 'property_subtype', '').lower()

        tr_with_dash = TR_WITH_DASHES.get(res['property_subtype'])
        if tr_with_dash:
            res['property_subtype'] = tr_with_dash

        return res

    @staticmethod
    def set_default_description(prop: Property, lang: str, trans_fields: dict)\
        -> dict:
        """Set default description for scraped properties"""
        if not prop.description and prop.scraped:
            trans_fields['txt'] = get_translation_in(
                TR_DEFAULT_DESCRIPTION, lang
            )
        return trans_fields

    @staticmethod
    def update_new_languages(prop: Property, prop_info: dict):
        """Translate prop info with new languages"""
        prop_translate = GoogleTranslate(prop)
        return prop_translate.retrieve_google_translations(
            SOURCE_LANGUAGE,
            NEW_LANGUAGES,
            list(prop_info.values()),
            tuple(prop_info.keys())
        ) or {}

    def update_desc_translations(self, translations: dict):
        """Update description property obj with new languages translations"""
        self.instance.translations.update(translations)
        self.instance.save()


class PropertyListSerializer(serializers.ModelSerializer):
    location = PointFieldSerializer()
    photos = serializers.SerializerMethodField()
    files = serializers.SerializerMethodField()

    class Meta:
        model = Property
        exclude = ['org_property_type', 'org_property_subtype']

    def get_photos(self, obj):
        return [photo.photo.url for photo in obj.photos.all().order_by('order')]

    @staticmethod
    def get_files(obj):
        return [file.file.url for file in obj.files.all().order_by('order')]


class PropertyDetailSerializer(serializers.ModelSerializer):
    location = PointFieldSerializer()
    photos = serializers.SerializerMethodField()
    files = serializers.SerializerMethodField()
    agent = serializers.SerializerMethodField()
    description_translation = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()

    class Meta:
        model = Property
        exclude = ['org_property_type', 'org_property_subtype']

    def get_photos(self, obj):
        return [photo.photo.url for photo in obj.photos.all().order_by('order')]

    @staticmethod
    def get_files(obj):
        return [file.file.url for file in obj.files.all().order_by('order')]

    @staticmethod
    def get_agent(obj):
        return AgentSearchSerializer(obj._agent).data

    @staticmethod
    def get_address(obj):
        if not obj.address:
            return obj.full_address

        return obj.address

    @staticmethod
    def get_description_translation(obj):
        # Creates PropertyDescTranslation with property title translations
        if not hasattr(obj, 'description_translation'):
            prop_translation = GoogleTranslate(obj)
            prop_translation.save_translation()
        return PropertyDescTranslationSerializer(obj.description_translation).\
            data


class PropertySearchSerializer(PropertyListSerializer):
    agent = AgentSearchSerializer(read_only=True)

    class Meta:
        model = Property
        fields = [
            'id',
            'photos',
            'price',
            'price_currency',
            'price_min',
            'price_max',
            'price_min_currency',
            'price_max_currency',
            'monthly_hoa_fee',
            'monthly_hoa_fee_currency',
            'monthly_hoa_fee_min',
            'monthly_hoa_fee_max',
            'monthly_hoa_fee_min_currency',
            'monthly_hoa_fee_max_currency',
            'country',
            'city',
            'street',
            'region',
            'baths',
            'baths_min',
            'baths_max',
            'beds',
            'beds_min',
            'beds_max',
            'lot_size',
            'lot_size_min',
            'lot_size_max',
            'agent',
            'buy_rent',
            'location'
        ]


class PropertySearchMyPropertiesSerializer(PropertyListSerializer):
    agent = AgentSearchSerializer()  # override for minimal agent info required for search endpoint
    payment = PaymentReadOnlySerializer()
    subscription = SubscriptionReadOnlySerializer()

    class Meta:
        model = Property
        fields = [
            'id', 'beds', 'beds_min', 'beds_max', 'size',
            'lot_size', 'lot_size_min', 'lot_size_max', 'baths',
            'baths_min', 'baths_max', 'price', 'price_min', 'price_max',
            'price_currency', 'price_min_currency', 'price_max_currency',
            'country', 'region', 'city', 'street', 'full_address',
            'location', 'agent', 'monthly_hoa_fee', 'monthly_hoa_fee_currency',
            'photos', 'files', 'status', 'website_link', 'live_tour_link', 'grm',
            'cap_rate', 'payment', 'paid_from', 'paid_to', 'property_subtype',
            'property_type', 'subscription', 'free_marketing', 'tenancy',
            'building_area', 'parking_space',
        ]


class PropertyInsertUpdateSerializer(serializers.ModelSerializer):
    location = PointFieldSerializer()

    class Meta:
        model = Property
        exclude = ['org_property_type', 'org_property_subtype']
        extra_kwargs = {
            'id': {'read_only': True},
            'updated_at': {'read_only': True},
            'created_at': {'read_only': True},
            'rating_avg': {'read_only': True},
            'paid_from': {'read_only': True},
            'paid_to': {'read_only': True},
            'payment': {'read_only': True},
        }

    def save(self, **kwargs):
        instance = super().save(**kwargs)
        gg = GoogleGeocoding(instance, reverse=False)
        gg.save_geocoding_data()
        instance.refresh_from_db()
        return instance

    def validate(self, attrs):
        val_data = super().validate(attrs)

        if self.context['request'].method in ['PUT', 'PATCH']:
            prop_pk = int(self.context['view'].kwargs['pk'])
            prop_obj = Property.objects.get(pk=prop_pk)

            if prop_obj.status == STATUS_ACTIVE and prop_obj.subscription:
                self.subscription_validation(self.get_property_sub(prop_obj))

        if attrs.get('property_type') == TYPE_RESIDENTIAL:
            self.grm_validation(attrs.get('grm'))
            self.cap_rate_validation(attrs.get('cap_rate'))

        return val_data

    @staticmethod
    def grm_validation(grm):
        if grm is not None:
            raise serializers.ValidationError({
                'grm': f'This field should be null for {TYPE_RESIDENTIAL}'
                       f' property.'
            })

    @staticmethod
    def cap_rate_validation(cap_rate):
        if cap_rate is not None:
            raise serializers.ValidationError({
                'cap_rate': f'This field should be null for {TYPE_RESIDENTIAL}'
                            f' property.'
            })

    @staticmethod
    def subscription_validation(sub):
        if sub is None:
            raise serializers.ValidationError({
                "subscription": "Can't update property without subscription."
            })

    @staticmethod
    def get_property_sub(prop_obj: Property) -> Property.subscription:
        return prop_obj.subscription


class PropertyPhotoUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyPhoto
        fields = ["photo", "order"]


class PropertyPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyPhoto
        fields = "__all__"


class PropertyFileUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyFile
        fields = ["file", "order"]


class PropertyFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyFile
        fields = "__all__"


class UserSavedPropertyPostSerializer(serializers.Serializer):
    property_id = serializers.IntegerField(allow_null=False, required=True)
    notes = serializers.CharField(allow_blank=True, allow_null=True, required=False)

    def create(self, validated_data):
        property_ = get_object_or_404(
            Property,
            id=validated_data['property_id']
        )

        obj = UserSavedProperty(
            **validated_data,
            user_id=self.context['user_id'],
            last_updated_at=property_.updated_at,
            last_status=property_.status
        )
        obj.save()
        return obj


class UserSavedPropertySerializer(serializers.ModelSerializer):
    property_updated_at = serializers.DateTimeField(source='property.updated_at', read_only=True)
    property_status = serializers.CharField(source='property.status', read_only=True)
    is_changed = serializers.SerializerMethodField()

    class Meta:
        model = UserSavedProperty
        exclude = ['id']
        extra_kwargs = {
            'id': {'read_only': True},
            'updated_at': {'read_only': True},
            'created_at': {'read_only': True},
            'user_id': {'read_only': True},
            'property_updated_at': {'read_only': True},
            'property_status': {'read_only': True},

        }

    def get_is_changed(self, obj):
        return (
            obj.last_updated_at != obj.property.updated_at
            or obj.last_status != obj.property.status
        )


class PropertiesFileUploadSerializer(serializers.ModelSerializer):

    class Meta:
        model = ScrapedPropertiesFile
        fields = ('file',)

    def create(self, validated_data):
        instance = super().create(validated_data)
        import_properties_from_file.delay(instance.id)
        return instance


class PropertiesFileUpdateRentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScrapedPropertiesFile
        fields = ('file',)

    def create(self, validated_data):
        instance = super().create(validated_data)
        update_rent_properties_from_file.delay(instance.id)
        return instance


class PropertyLocationSerializer(serializers.ModelSerializer):
    location = PointFieldSerializer()

    class Meta:
        model = Property
        fields = ['id', 'location', "status"]


class PropertyLowDetailedSerializer(serializers.ModelSerializer):
    location = PointFieldSerializer()
    address = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            'id', 'location', 'city', 'country', 'price', 'price_currency',
            'address',
        ]

    @staticmethod
    def get_address(obj):
        if not obj.address:
            return obj.full_address

        return obj.address
