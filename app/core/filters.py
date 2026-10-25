"""Filter global dashboard (dipakai semua halaman).

Semua endpoint menerima query param yang sama:
date_from, date_to, year, month, state, category.

`build_fact_source` mengganti tabel `fact_order_items` dengan subquery yang
sudah terfilter, jadi query lama cukup memakai hasilnya sebagai pengganti
nama tabel. Nilai filter selalu lewat query parameter (aman dari SQL injection).
"""
from dataclasses import dataclass
from datetime import date

from fastapi import Query
from google.cloud import bigquery

from app.core.config import PROJECT_ID, DATASET_ID


@dataclass(frozen=True)
class Filters:
    date_from: date | None = None
    date_to: date | None = None
    year: int | None = None
    month: int | None = None
    state: str | None = None
    category: str | None = None


def get_filters(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    state: str | None = Query(default=None, min_length=2, max_length=2),
    category: str | None = Query(default=None, max_length=100),
) -> Filters:
    """Dipakai sebagai dependency FastAPI: `filters: Filters = Depends(get_filters)`."""
    return Filters(
        date_from=date_from,
        date_to=date_to,
        year=year,
        month=month,
        state=state.upper() if state else None,
        category=category,
    )


def build_fact_source(filters: Filters | None):
    """Return (sql_source, query_parameters).

    sql_source bisa langsung dipakai setelah FROM, mis.
    `FROM {sql_source} AS f`. Tanpa filter, hasilnya tabel asli.
    """
    table = f"`{PROJECT_ID}.{DATASET_ID}.fact_order_items`"
    if filters is None:
        return table, []

    joins: list[str] = []
    where: list[str] = []
    params: list = []

    if filters.date_from:
        where.append("f.order_date >= @flt_date_from")
        params.append(bigquery.ScalarQueryParameter("flt_date_from", "DATE", filters.date_from))
    if filters.date_to:
        where.append("f.order_date <= @flt_date_to")
        params.append(bigquery.ScalarQueryParameter("flt_date_to", "DATE", filters.date_to))
    if filters.year:
        where.append("EXTRACT(YEAR FROM f.order_date) = @flt_year")
        params.append(bigquery.ScalarQueryParameter("flt_year", "INT64", filters.year))
    if filters.month:
        where.append("EXTRACT(MONTH FROM f.order_date) = @flt_month")
        params.append(bigquery.ScalarQueryParameter("flt_month", "INT64", filters.month))
    if filters.state:
        joins.append(
            f"JOIN `{PROJECT_ID}.{DATASET_ID}.dim_customers` AS flt_c "
            "ON f.customer_id = flt_c.customer_id"
        )
        where.append("flt_c.customer_state = @flt_state")
        params.append(bigquery.ScalarQueryParameter("flt_state", "STRING", filters.state))
    if filters.category:
        joins.append(
            f"JOIN `{PROJECT_ID}.{DATASET_ID}.dim_products` AS flt_p "
            "ON f.product_id = flt_p.product_id"
        )
        where.append("flt_p.product_category = @flt_category")
        params.append(bigquery.ScalarQueryParameter("flt_category", "STRING", filters.category))

    if not where:
        return table, []

    source = (
        f"(SELECT f.* FROM {table} AS f "
        + " ".join(joins)
        + " WHERE "
        + " AND ".join(where)
        + ")"
    )
    return source, params


def job_config(params: list) -> bigquery.QueryJobConfig | None:
    return bigquery.QueryJobConfig(query_parameters=params) if params else None
