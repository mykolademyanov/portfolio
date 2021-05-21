import pytest
from faker import Factory
from factory import DjangoModelFactory, SubFactory
from pgr_django.users.models import Agent, Broker
from ..models import Property
from .. import constants

import random

random.seed(1)

pytestmark = pytest.mark.django_db
faker = Factory.create()


class BrokerFactory(DjangoModelFactory):
    email = faker.email()

    class Meta:
        model = Broker


class AgentFactory(DjangoModelFactory):
    first_name = faker.first_name()
    last_name = faker.last_name()
    # broker = SubFactory(BrokerFactory)

    class Meta:
        model = Agent


class PropertyFactory(DjangoModelFactory):
    property_type = constants.TYPE_RESIDENTIAL[1]
    property_subtype = faker.random_element([t[1] for t in constants.TYPE_SUBTYPE_MAP[constants.TYPE_RESIDENTIAL]])
    status = constants.STATUS_INACTIVE
    price = faker.pydecimal(left_digits=8, right_digits=2, positive=True)
    monthly_hoa_fee = faker.pydecimal(left_digits=8, right_digits=2, positive=True)
    country = faker.country()
    region = faker.pystr(10)
    city = faker.city()
    district = faker.pystr(10)
    zip_code = faker.postcode()
    street = faker.street_name()
    beds = faker.pyint(0, 10)
    baths = faker.pyint(0, 10)
    size = faker.pydecimal(left_digits=8, right_digits=2, positive=True)
    lot_size = faker.pydecimal(left_digits=8, right_digits=2, positive=True)
    build_year = faker.pyint(1700, 2020)
    amenities = faker.paragraph(nb_sentences=3, variable_nb_sentences=True, ext_word_list=None)
    description = faker.paragraph(nb_sentences=3, variable_nb_sentences=True, ext_word_list=None)
    run_token = faker.pystr()
    buy_rent = faker.random_element(['buy', 'rent'])
    realtor_agent_id = None

    class Meta:
        model = Property
