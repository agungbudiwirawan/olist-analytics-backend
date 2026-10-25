from functools import lru_cache

from app.core.filters import Filters
from app.repositories import kpi_repository


def get_kpi(filters: Filters | None = None):
    return kpi_repository.get_kpi_data(filters)


def get_monthly_sales(filters: Filters | None = None):
    return kpi_repository.get_monthly_sales(filters)


def get_overview_dashboard(filters: Filters | None = None):
    return kpi_repository.get_overview_dashboard(filters)


@lru_cache(maxsize=1)
def get_filter_options():
    # Opsi filter jarang berubah, cukup diambil sekali per proses server.
    return kpi_repository.get_filter_options()
