import pytest

from recommender.catalog import Catalog
from recommender.model import RecommendationModel
from recommender.service import RecommendationService


@pytest.fixture(scope="session")
def service():
    catalog = Catalog()
    return RecommendationService(catalog, RecommendationModel().fit(catalog))

