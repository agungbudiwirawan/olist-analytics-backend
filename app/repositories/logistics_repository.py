from app.repositories.kpi_repository import client
from app.core.config import PROJECT_ID, DATASET_ID
from app.core.filters import Filters, build_fact_source, job_config


def get_logistics_dashboard_data(filters: Filters | None = None):
    fact, params = build_fact_source(filters)
    customers = f"`{PROJECT_ID}.{DATASET_ID}.dim_customers`"
    sellers = f"`{PROJECT_ID}.{DATASET_ID}.dim_sellers`"

    # One row per order for KPIs/monthly trends, avoiding item-level duplication.
    order_base = f"""
        WITH orders AS (
            SELECT
                f.order_id,
                ANY_VALUE(f.order_status) AS order_status,
                ANY_VALUE(f.order_purchase_timestamp) AS purchased_at,
                ANY_VALUE(f.order_delivered_carrier_date) AS carrier_at,
                ANY_VALUE(f.order_delivered_customer_date) AS delivered_at,
                ANY_VALUE(f.order_estimated_delivery_date) AS estimated_at,
                SUM(f.freight_value) AS freight_cost
            FROM {fact} f
            WHERE f.order_id IS NOT NULL
            GROUP BY f.order_id
        )
    """

    kpi_query = order_base + """
        SELECT
            COUNTIF(order_status = 'delivered') AS delivered_orders,
            ROUND(AVG(IF(
                order_status = 'delivered'
                AND purchased_at IS NOT NULL
                AND delivered_at IS NOT NULL,
                TIMESTAMP_DIFF(delivered_at, purchased_at, HOUR) / 24.0,
                NULL
            )), 2) AS avg_delivery_lead_time_days,
            ROUND(AVG(IF(
                order_status = 'delivered'
                AND carrier_at IS NOT NULL
                AND delivered_at IS NOT NULL,
                TIMESTAMP_DIFF(delivered_at, carrier_at, HOUR) / 24.0,
                NULL
            )), 2) AS avg_carrier_transit_days,
            ROUND(AVG(IF(
                order_status = 'delivered'
                AND purchased_at IS NOT NULL
                AND carrier_at IS NOT NULL,
                TIMESTAMP_DIFF(carrier_at, purchased_at, HOUR) / 24.0,
                NULL
            )), 2) AS avg_purchase_to_carrier_days,
            ROUND(100 * SAFE_DIVIDE(
                COUNTIF(
                    order_status = 'delivered'
                    AND delivered_at IS NOT NULL
                    AND estimated_at IS NOT NULL
                    AND delivered_at <= estimated_at
                ),
                COUNTIF(
                    order_status = 'delivered'
                    AND delivered_at IS NOT NULL
                    AND estimated_at IS NOT NULL
                )
            ), 2) AS on_time_delivery_rate_pct,
            ROUND(SUM(IF(order_status = 'delivered', freight_cost, 0)), 2)
                AS delivered_freight_cost
        FROM orders
    """

    monthly_query = order_base + """
        SELECT
            FORMAT_DATE('%Y-%m', DATE(purchased_at)) AS month,
            COUNTIF(order_status = 'delivered') AS delivered_orders,
            ROUND(100 * SAFE_DIVIDE(
                COUNTIF(order_status = 'delivered'
                    AND delivered_at IS NOT NULL
                    AND estimated_at IS NOT NULL
                    AND delivered_at <= estimated_at),
                COUNTIF(order_status = 'delivered'
                    AND delivered_at IS NOT NULL
                    AND estimated_at IS NOT NULL)
            ), 2) AS on_time_delivery_rate_pct,
            ROUND(AVG(IF(
                order_status = 'delivered'
                AND purchased_at IS NOT NULL
                AND delivered_at IS NOT NULL,
                TIMESTAMP_DIFF(delivered_at, purchased_at, HOUR) / 24.0,
                NULL
            )), 2) AS avg_delivery_lead_time_days,
            ROUND(AVG(IF(
                order_status = 'delivered'
                AND carrier_at IS NOT NULL
                AND delivered_at IS NOT NULL,
                TIMESTAMP_DIFF(delivered_at, carrier_at, HOUR) / 24.0,
                NULL
            )), 2) AS avg_carrier_transit_days,
            ROUND(SUM(IF(order_status = 'delivered', freight_cost, 0)), 2)
                AS total_freight_cost
        FROM orders
        WHERE purchased_at IS NOT NULL
        GROUP BY month
        ORDER BY month
    """

    regional_query = f"""
        WITH orders AS (
            SELECT
                f.order_id,
                ANY_VALUE(f.order_status) AS order_status,
                ANY_VALUE(f.order_purchase_timestamp) AS purchased_at,
                ANY_VALUE(f.order_delivered_carrier_date) AS carrier_at,
                ANY_VALUE(f.order_delivered_customer_date) AS delivered_at,
                ANY_VALUE(f.order_estimated_delivery_date) AS estimated_at,
                ANY_VALUE(f.customer_id) AS customer_id,
                SUM(f.freight_value) AS freight_cost
            FROM {fact} f
            WHERE f.order_id IS NOT NULL
            GROUP BY f.order_id
        )
        SELECT
            c.customer_state AS destination_state,
            COUNTIF(o.order_status = 'delivered') AS delivered_orders,
            ROUND(100 * SAFE_DIVIDE(
                COUNTIF(o.order_status = 'delivered'
                    AND o.delivered_at IS NOT NULL
                    AND o.estimated_at IS NOT NULL
                    AND o.delivered_at <= o.estimated_at),
                COUNTIF(o.order_status = 'delivered'
                    AND o.delivered_at IS NOT NULL
                    AND o.estimated_at IS NOT NULL)
            ), 2) AS on_time_delivery_rate_pct,
            ROUND(AVG(IF(
                o.order_status = 'delivered' AND o.purchased_at IS NOT NULL
                AND o.delivered_at IS NOT NULL,
                TIMESTAMP_DIFF(o.delivered_at, o.purchased_at, HOUR) / 24.0,
                NULL
            )), 2) AS avg_delivery_lead_time_days,
            ROUND(AVG(IF(
                o.order_status = 'delivered' AND o.carrier_at IS NOT NULL
                AND o.delivered_at IS NOT NULL,
                TIMESTAMP_DIFF(o.delivered_at, o.carrier_at, HOUR) / 24.0,
                NULL
            )), 2) AS avg_carrier_transit_days,
            ROUND(AVG(IF(
                o.order_status = 'delivered' AND o.purchased_at IS NOT NULL
                AND o.carrier_at IS NOT NULL,
                TIMESTAMP_DIFF(o.carrier_at, o.purchased_at, HOUR) / 24.0,
                NULL
            )), 2) AS avg_purchase_to_carrier_days,
            ROUND(AVG(IF(o.order_status = 'delivered', o.freight_cost, NULL)), 2)
                AS avg_freight_cost_per_order,
            ROUND(SUM(IF(o.order_status = 'delivered', o.freight_cost, 0)), 2)
                AS total_freight_cost
        FROM orders o
        JOIN {customers} c ON o.customer_id = c.customer_id
        WHERE c.customer_state IS NOT NULL
        GROUP BY destination_state
        HAVING COUNTIF(o.order_status = 'delivered') > 0
        ORDER BY delivered_orders DESC
    """

    route_query = f"""
        WITH order_routes AS (
            SELECT
                f.order_id,
                s.seller_state AS origin_state,
                c.customer_state AS destination_state,
                ANY_VALUE(f.order_status) AS order_status,
                ANY_VALUE(f.order_purchase_timestamp) AS purchased_at,
                ANY_VALUE(f.order_delivered_carrier_date) AS carrier_at,
                ANY_VALUE(f.order_delivered_customer_date) AS delivered_at,
                SUM(f.freight_value) AS freight_cost,
                COUNT(*) AS total_items
            FROM {fact} f
            JOIN {sellers} s ON f.seller_id = s.seller_id
            JOIN {customers} c ON f.customer_id = c.customer_id
            WHERE f.seller_id IS NOT NULL
              AND f.customer_id IS NOT NULL
              AND s.seller_state IS NOT NULL
              AND c.customer_state IS NOT NULL
            GROUP BY f.order_id, origin_state, destination_state
        )
        SELECT
            origin_state,
            destination_state,
            COUNT(DISTINCT order_id) AS total_orders,
            SUM(total_items) AS total_items,
            ROUND(AVG(IF(
                order_status = 'delivered' AND carrier_at IS NOT NULL
                AND delivered_at IS NOT NULL,
                TIMESTAMP_DIFF(delivered_at, carrier_at, HOUR) / 24.0,
                NULL
            )), 2) AS avg_carrier_transit_days,
            ROUND(AVG(IF(
                order_status = 'delivered' AND purchased_at IS NOT NULL
                AND delivered_at IS NOT NULL,
                TIMESTAMP_DIFF(delivered_at, purchased_at, HOUR) / 24.0,
                NULL
            )), 2) AS avg_delivery_lead_time_days,
            ROUND(AVG(IF(order_status = 'delivered', freight_cost, NULL)), 2)
                AS avg_freight_cost_per_order,
            ROUND(SUM(IF(order_status = 'delivered', freight_cost, 0)), 2)
                AS total_freight_cost
        FROM order_routes
        GROUP BY origin_state, destination_state
        HAVING COUNT(DISTINCT IF(order_status = 'delivered', order_id, NULL)) >= 30
           AND COUNTIF(order_status = 'delivered'
                AND carrier_at IS NOT NULL AND delivered_at IS NOT NULL) >= 30
        ORDER BY avg_carrier_transit_days DESC
    """

    def rows(query):
        return [
            dict(row.items())
            for row in client.query(query, job_config=job_config(params)).result()
        ]

    kpi_rows = rows(kpi_query)
    return {
        "kpis": kpi_rows[0] if kpi_rows else {},
        "monthly": rows(monthly_query),
        "regional": rows(regional_query),
        "routes": rows(route_query),
    }
