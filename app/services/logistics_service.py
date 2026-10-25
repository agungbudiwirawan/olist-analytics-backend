from app.core.filters import Filters
from app.repositories import logistics_repository


def get_logistics_dashboard(filters: Filters | None = None):
    return logistics_repository.get_logistics_dashboard_data(filters)
