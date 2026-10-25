
from app.repositories.kpi_repository import client
from app.core.config import PROJECT_ID, DATASET_ID
from app.core.filters import Filters, build_fact_source, job_config



def get_product_categories_data(filters: Filters | None = None):
    fact_source, params = build_fact_source(filters)
    query = f"""
        WITH category_metrics AS (
            SELECT
                COALESCE(p.product_category, 'Unknown') AS category,
                ROUND(SUM(f.price), 2) AS revenue,
                ROUND(SUM(f.freight_value), 2) AS freight_cost,
                COUNT(*) AS items_sold,
                COUNT(DISTINCT f.order_id) AS total_orders,
                COUNT(DISTINCT f.product_id) AS product_count,
                ROUND(AVG(f.price), 2) AS avg_item_price
            FROM {fact_source} AS f
            LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.dim_products` AS p
                ON f.product_id = p.product_id
            GROUP BY category
        )
        SELECT
            *,
            ROUND(
                SAFE_DIVIDE(
                    revenue,
                    SUM(revenue) OVER ()
                ) * 100,
                2
            ) AS revenue_share
        FROM category_metrics
        ORDER BY revenue DESC
    """

    result = client.query(query, job_config=job_config(params)).result()

    return [
        {
            "category": row.category,
            "revenue": float(row.revenue or 0),
            "freight_cost": float(row.freight_cost or 0),
            "items_sold": int(row.items_sold or 0),
            "total_orders": int(row.total_orders or 0),
            "product_count": int(row.product_count or 0),
            "avg_item_price": float(row.avg_item_price or 0),
            "revenue_share": float(row.revenue_share or 0),
        }
        for row in result
    ]
