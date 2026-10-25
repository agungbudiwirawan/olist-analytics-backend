from concurrent.futures import ThreadPoolExecutor

from google.cloud import bigquery

from app.core.config import PROJECT_ID, DATASET_ID
from app.core.filters import Filters, build_fact_source, job_config

client = bigquery.Client(project=PROJECT_ID)

DIM_CUSTOMERS = f"`{PROJECT_ID}.{DATASET_ID}.dim_customers`"
DIM_PRODUCTS = f"`{PROJECT_ID}.{DATASET_ID}.dim_products`"


def get_kpi_data(filters: Filters | None = None):
    fact, params = build_fact_source(filters)
    query = f"""
        SELECT
            SUM(total_item_value) AS total_sales,
            COUNT(DISTINCT order_id) AS total_orders,
            COUNT(*) AS total_items,
            SUM(freight_value) AS total_freight
        FROM {fact}
    """

    row = next(iter(client.query(query, job_config=job_config(params)).result()))

    return {
        "total_sales": round(row.total_sales or 0, 2),
        "total_orders": row.total_orders or 0,
        "total_items": row.total_items or 0,
        "total_freight": round(row.total_freight or 0, 2),
    }


def get_monthly_sales(filters: Filters | None = None):
    fact, params = build_fact_source(filters)
    query = f"""
        SELECT
            FORMAT_DATE('%Y-%m', order_date) AS month,
            ROUND(SUM(total_item_value), 2) AS total_sales,
            COUNT(DISTINCT order_id) AS total_orders
        FROM {fact}
        WHERE order_date IS NOT NULL
        GROUP BY month
        ORDER BY month
    """

    result = client.query(query, job_config=job_config(params)).result()

    return [
        {
            "month": row.month,
            "total_sales": float(row.total_sales or 0),
            "total_orders": row.total_orders or 0,
        }
        for row in result
    ]


def get_sales_by_category(filters: Filters | None = None, limit: int = 10):
    fact, params = build_fact_source(filters)
    query = f"""
        SELECT
            COALESCE(p.product_category, 'Unknown') AS category,
            ROUND(SUM(f.total_item_value), 2) AS revenue,
            COUNT(DISTINCT f.order_id) AS total_orders,
            COUNT(*) AS items_sold
        FROM {fact} AS f
        LEFT JOIN {DIM_PRODUCTS} AS p ON f.product_id = p.product_id
        GROUP BY category
        ORDER BY revenue DESC
        LIMIT {int(limit)}
    """
    rows = client.query(query, job_config=job_config(params)).result()
    return [
        {
            "category": row.category,
            "revenue": float(row.revenue or 0),
            "total_orders": int(row.total_orders or 0),
            "items_sold": int(row.items_sold or 0),
        }
        for row in rows
    ]


def get_sales_by_state(filters: Filters | None = None):
    fact, params = build_fact_source(filters)
    query = f"""
        SELECT
            c.customer_state AS state,
            ROUND(SUM(f.total_item_value), 2) AS revenue,
            COUNT(DISTINCT f.order_id) AS total_orders
        FROM {fact} AS f
        JOIN {DIM_CUSTOMERS} AS c ON f.customer_id = c.customer_id
        WHERE c.customer_state IS NOT NULL
        GROUP BY state
        ORDER BY revenue DESC
    """
    rows = client.query(query, job_config=job_config(params)).result()
    return [
        {
            "state": row.state,
            "revenue": float(row.revenue or 0),
            "total_orders": int(row.total_orders or 0),
        }
        for row in rows
    ]


def get_order_status(filters: Filters | None = None):
    fact, params = build_fact_source(filters)
    query = f"""
        SELECT
            COALESCE(order_status, 'unknown') AS status,
            COUNT(DISTINCT order_id) AS total_orders
        FROM {fact}
        WHERE order_id IS NOT NULL
        GROUP BY status
        ORDER BY total_orders DESC
    """
    rows = client.query(query, job_config=job_config(params)).result()
    return [
        {"status": row.status, "total_orders": int(row.total_orders or 0)}
        for row in rows
    ]


def get_overview_dashboard(filters: Filters | None = None):
    """Jalankan 5 query sekaligus (paralel) supaya halaman Overview cepat."""
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            "kpis": pool.submit(get_kpi_data, filters),
            "monthly": pool.submit(get_monthly_sales, filters),
            "categories": pool.submit(get_sales_by_category, filters),
            "states": pool.submit(get_sales_by_state, filters),
            "order_status": pool.submit(get_order_status, filters),
        }
        return {name: future.result() for name, future in futures.items()}


def get_filter_options():
    """Opsi untuk filter bar: rentang tanggal data + daftar kategori."""
    fact = f"`{PROJECT_ID}.{DATASET_ID}.fact_order_items`"
    date_row = next(iter(client.query(f"""
        SELECT MIN(order_date) AS min_date, MAX(order_date) AS max_date
        FROM {fact}
    """).result()))

    categories = [
        row.product_category
        for row in client.query(f"""
            SELECT DISTINCT product_category
            FROM {DIM_PRODUCTS}
            WHERE product_category IS NOT NULL
            ORDER BY product_category
        """).result()
    ]

    return {
        "min_date": date_row.min_date.isoformat() if date_row.min_date else None,
        "max_date": date_row.max_date.isoformat() if date_row.max_date else None,
        "categories": categories,
    }
