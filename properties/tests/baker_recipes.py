from model_bakery.recipe import Recipe, foreign_key

from pgr_django.users.tests.baker_recipes import AgentRecipe

from ..models import Property

PropertyRecipe = Recipe(Property, agent=foreign_key(AgentRecipe))
