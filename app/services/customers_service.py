from app.core.filters import Filters
from app.repositories import customers_repository


def get_customer_dashboard(filters: Filters | None = None):
    return customers_repository.get_customer_dashboard_data(filters)
