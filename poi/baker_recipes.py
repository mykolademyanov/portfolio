from model_bakery.recipe import Recipe, foreign_key

from poi.models import LocationType, Location, LocationHistory

LocationTypeRecipe = Recipe(LocationType, color="#ffffff")
LocationRecipe = Recipe(
    Location, type=foreign_key(LocationTypeRecipe), radius=None
)
LocationHistoryRecipe = Recipe(
    LocationHistory, location=foreign_key(LocationRecipe)
)
