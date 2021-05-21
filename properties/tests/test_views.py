import random

from django.core.cache import cache
from django.urls import reverse
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from .baker_recipes import PropertyRecipe

from ..models import Property
from ..constants import TYPE_SUBTYPE_MAP, TYPE_RESIDENTIAL, TYPE_COMMERCIAL
from pgr_django.users.tests import AgentRecipe, BrokerRecipe, UserRecipe


class TestPropertyEdit(TestCase):

    def setUp(self):
        self.url = "properties:patch"
        self.client = APIClient()
        self.broker = BrokerRecipe.make(user__is_broker=True)
        self.diff_broker = BrokerRecipe.make(user__is_broker=True)
        self.agent = AgentRecipe.make(user__is_agent=True, broker=self.broker)
        self.diff_agent = AgentRecipe.make(
            user__is_agent=True, broker=self.diff_broker
        )
        self.property = PropertyRecipe.make(
            agent=self.agent,
            property_type=TYPE_RESIDENTIAL,
            property_subtype=random.choice(
                TYPE_SUBTYPE_MAP.get(TYPE_RESIDENTIAL)
            )
        )
        self.client.force_login(user=self.diff_agent.user)

    def test_property_agent_success_edit(self):
        """
        Test for checking agent ability to edit his props
        """
        desc_for_edit = "Test desc"
        self.assertNotEqual(self.property.description, desc_for_edit)
        self.client.force_login(self.agent.user)
        response = self.client.patch(
            reverse(self.url, kwargs={"pk": self.property.pk}),
            {"description": desc_for_edit}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.property.refresh_from_db()
        self.assertEqual(self.property.description, desc_for_edit)

    def test_property_edit_diff_agent(self):
        """
        Test for checking that agent is unable to edit another agent's prop
        """
        response = self.client.patch(
            reverse(self.url, kwargs={"pk": self.property.pk}),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_prop_edit_any_brokers(self):
        """
        Test for checking whether agent without broker can't edit property
        of another agent without broker
        """
        self.agent.broker = self.diff_agent.broker = None
        self.agent.save()
        self.diff_agent.save()
        response = self.client.patch(
            reverse(self.url, kwargs={"pk": self.property.pk}),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_prop_edit_same_brokers(self):
        """
        Test for checking ability of different agents with same broker update
        prop of each other
        """
        desc_for_edit = "Same brokers"
        self.diff_agent.broker = self.broker
        self.diff_agent.save()
        self.assertNotEqual(self.property.description, desc_for_edit)
        response = self.client.patch(
            reverse(self.url, kwargs={"pk": self.property.pk}),
            {"description": desc_for_edit}
        )

        self.property.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.property.description, desc_for_edit)

    def test_prop_edit_diff_brokers(self):
        """
        Test for checking that agents with different brokers are not allowed to
        update each others properties
        """
        response = self.client.patch(
            reverse(self.url, kwargs={"pk": self.property.pk}),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TestPropertyCreate(TestCase):

    def setUp(self):
        self.url = "properties:create"
        self.client = APIClient()
        self.agent = AgentRecipe.make(user__is_agent=True)
        self.client.force_login(self.agent.user)
        self.broker = BrokerRecipe.make(user__is_broker=True)
        self.prop_data = {
            "location": {
                "lat": 11.12,
                "lng": 78.22
            },
            "property_type": TYPE_RESIDENTIAL,
            "property_subtype": random.choice(
                TYPE_SUBTYPE_MAP.get(TYPE_RESIDENTIAL)
            ),
        }

    def test_customer_prop_create(self):
        """
        Test for checking that customer hasn't permission to create prop
        """
        customer = UserRecipe.make()
        self.client.force_login(customer)
        response = self.client.post(
            reverse(self.url), data=self.prop_data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_broker_prop_create(self):
        """
        Test for checking broker's ability to create prop
        """
        self.assertEqual(Property.objects.count(), 0)
        self.client.force_login(self.broker.user)
        response = self.client.post(
            reverse(self.url), data=self.prop_data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Property.objects.count(), 1)

    def test_residential_prop_create_success(self):
        """
        Test for checking ability of agent to create prop with residential type
        """
        self.assertEqual(Property.objects.count(), 0)
        response = self.client.post(
            reverse(self.url), data=self.prop_data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        props = Property.objects.all()
        self.assertEqual(props.count(), 1)
        self.assertEqual(props.first().property_type, TYPE_RESIDENTIAL)

    def test_commercial_prop_create_success(self):
        """
        Test for checking ability of agent to create prop with commercial type
        """
        self.assertEqual(Property.objects.count(), 0)
        self.prop_data.update({
            "property_type": TYPE_COMMERCIAL,
            "property_subtype": random.choice(
                TYPE_SUBTYPE_MAP.get(TYPE_COMMERCIAL)
            )
        })
        response = self.client.post(
            reverse(self.url), data=self.prop_data, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        props = Property.objects.all()
        self.assertEqual(props.count(), 1)
        self.assertEqual(props.first().property_type, TYPE_COMMERCIAL)


class TestListProperty(TestCase):
    @staticmethod
    def create_properties(props_num: int):
        # create some properties to check list view
        agent = AgentRecipe.make(user__is_agent=True)
        [
            PropertyRecipe.make(
                agent=agent,
                property_type=TYPE_RESIDENTIAL,
                property_subtype=random.choice(
                    TYPE_SUBTYPE_MAP.get(TYPE_RESIDENTIAL)
                )
            )
            for _ in range(props_num)
        ]

    def setUp(self):
        self.client = APIClient()
        self.url = "properties:list"
        self.customer = UserRecipe.make(is_agent=False, is_broker=False)
        self.client.force_login(self.customer)
        cache.clear()

    def test_success_few_props_list(self):
        """
        Test for checking list view for small amount of props without next
        pagination
        """
        self.create_properties(6)
        response = self.client.get(
            reverse(self.url),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('count'), Property.objects.count())
        self.assertIsNone(response.data['links'].get('next'))
        self.assertEqual(len(response.data.get('items')), 6)

    def test_success_props_list(self):
        """
        Test for checking list view for a lot of props with next page
        pagination
        """
        default_pagination_limit = 30
        self.create_properties(37)
        response = self.client.get(
            reverse(self.url)
        )
        next_page_url = response.data['links'].get('next')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], Property.objects.count())
        self.assertIsNotNone(next_page_url)
        self.assertEqual(
            len(response.data['items']), default_pagination_limit
        )
        next_page_resp = self.client.get(next_page_url)
        self.assertEqual(next_page_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            len(next_page_resp.data['items']), 37 - default_pagination_limit
        )


class TestPropertyRetrieve(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = "properties:get"
        self.broker = BrokerRecipe.make(user__is_broker=True)
        self.agent = AgentRecipe.make(user__is_agent=True, broker=self.broker)
        self.prop = PropertyRecipe.make(
            agent=self.agent,
            property_type=TYPE_RESIDENTIAL,
            property_subtype=random.choice(
                TYPE_SUBTYPE_MAP.get(TYPE_RESIDENTIAL)
            )
        )

    def test_prop_retrieve_fail(self):
        """
        Test for checking prop detail fail
        """
        response = self.client.get(
            reverse(self.url, kwargs={"pk": self.prop.pk + 1})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get('detail'), "Not found.")

    def test_prop_retrieve_success(self):
        """
        Test for checking prop detail success
        """
        num_of_response_fields = 60
        response = self.client.get(
            reverse(self.url, kwargs={"pk": self.prop.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), num_of_response_fields)
