from app.core.filters import Filters
from app.repositories import products_repository


def get_product_categories(filters: Filters | None = None):
    return products_repository.get_product_categories_data(filters)
