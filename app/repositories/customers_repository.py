
from app.repositories.kpi_repository import client
from app.core.config import PROJECT_ID, DATASET_ID
from app.core.filters import Filters, build_fact_source, job_config


def get_customer_dashboard_data(filters: Filters | None = None):
    fact_source, params = build_fact_source(filters)
    query = f"""
        WITH order_customer AS (
            -- Satu baris per customer unik dan order.
            SELECT
                c.customer_unique_id,
                c.customer_state,
                c.customer_city,
                f.order_id,
                DATE(MAX(f.order_purchase_timestamp)) AS order_date,
                SUM(f.total_item_value) AS order_spending
            FROM {fact_source} AS f
            INNER JOIN `{PROJECT_ID}.{DATASET_ID}.dim_customers` AS c
                ON f.customer_id = c.customer_id
            WHERE
                c.customer_unique_id IS NOT NULL
                AND f.order_id IS NOT NULL
                AND f.order_purchase_timestamp IS NOT NULL
            GROUP BY
                c.customer_unique_id,
                c.customer_state,
                c.customer_city,
                f.order_id
        ),

        customer_metrics AS (
            SELECT
                customer_unique_id,
                COUNT(DISTINCT order_id) AS total_orders,
                SUM(order_spending) AS total_spending,
                MAX(order_date) AS last_order_date,
                MIN(order_date) AS first_order_date
            FROM order_customer
            GROUP BY customer_unique_id
        ),

        snapshot AS (
            SELECT MAX(order_date) AS snapshot_date
            FROM order_customer
        ),

        customer_profiles AS (
            SELECT
                customer_unique_id,
                ARRAY_AGG(
                    STRUCT(customer_state, customer_city)
                    ORDER BY customer_state, customer_city
                    LIMIT 1
                )[OFFSET(0)] AS profile
            FROM order_customer
            GROUP BY customer_unique_id
        ),

        state_metrics AS (
            SELECT
                profile.customer_state AS state,
                COUNT(*) AS customer_count
            FROM customer_profiles
            GROUP BY state
        ),

        city_metrics AS (
            SELECT
                profile.customer_city AS city,
                profile.customer_state AS state,
                COUNT(*) AS customer_count
            FROM customer_profiles
            GROUP BY city, state
        ),

        frequency_metrics AS (
            SELECT
                total_orders AS orders_per_customer,
                COUNT(*) AS customer_count
            FROM customer_metrics
            GROUP BY total_orders
        ),

        top_customers AS (
            SELECT
                customer_unique_id,
                total_orders,
                total_spending
            FROM customer_metrics
            ORDER BY total_spending DESC
            LIMIT 10
        ),

        kpis AS (
            SELECT
                COUNT(*) AS unique_customers,
                SUM(total_orders) AS total_orders,
                COUNTIF(total_orders > 1) AS repeat_customers,
                SUM(total_spending) AS total_spending
            FROM customer_metrics
        ),

        -- RFM scores: quintiles from 1 to 5.
        rfm_base AS (
            SELECT
                m.customer_unique_id,
                DATE_DIFF(s.snapshot_date, m.last_order_date, DAY)
                    AS recency_days,
                m.total_orders AS frequency,
                m.total_spending AS monetary
            FROM customer_metrics AS m
            CROSS JOIN snapshot AS s
        ),

        rfm_scored AS (
            SELECT
                *,
                -- Lower recency is better, so reverse its quintile score.
                6 - NTILE(5) OVER (
                    ORDER BY recency_days DESC, customer_unique_id
                ) AS r_score,
                NTILE(5) OVER (
                    ORDER BY frequency ASC, customer_unique_id
                ) AS f_score,
                NTILE(5) OVER (
                    ORDER BY monetary ASC, customer_unique_id
                ) AS m_score
            FROM rfm_base
        ),

        rfm_labeled AS (
            SELECT
                *,
                CASE
                    WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4
                        THEN 'Champions'
                    WHEN r_score >= 3 AND f_score >= 4
                        THEN 'Loyal Customers'
                    WHEN r_score >= 4 AND f_score BETWEEN 2 AND 3
                        THEN 'Potential Loyalists'
                    WHEN r_score = 5 AND f_score = 1
                        THEN 'Recent Customers'
                    WHEN r_score BETWEEN 2 AND 3 AND f_score BETWEEN 2 AND 3
                        THEN 'Need Attention'
                    WHEN r_score <= 2 AND f_score >= 3
                        THEN 'At Risk'
                    WHEN r_score <= 2 AND f_score <= 2
                        THEN 'Hibernating'
                    ELSE 'Others'
                END AS segment
            FROM rfm_scored
        ),

        rfm_metrics AS (
            SELECT
                segment,
                COUNT(*) AS customer_count
            FROM rfm_labeled
            GROUP BY segment
        ),

        cohort_customer_month AS (
            -- Deduplicate customer activity to one row per customer per month.
            SELECT DISTINCT
                customer_unique_id,
                DATE_TRUNC(order_date, MONTH) AS order_month
            FROM order_customer
        ),

        customer_cohorts AS (
            SELECT
                customer_unique_id,
                MIN(order_month) AS cohort_month
            FROM cohort_customer_month
            GROUP BY customer_unique_id
        ),

        cohort_sizes AS (
            SELECT
                cohort_month,
                COUNT(*) AS cohort_size
            FROM customer_cohorts
            GROUP BY cohort_month
        ),

        cohort_activity AS (
            SELECT
                cc.cohort_month,
                cm.order_month,
                DATE_DIFF(
                    cm.order_month,
                    cc.cohort_month,
                    MONTH
                ) AS months_since_first_order,
                COUNT(DISTINCT cm.customer_unique_id) AS active_customers
            FROM customer_cohorts AS cc
            INNER JOIN cohort_customer_month AS cm
                ON cc.customer_unique_id = cm.customer_unique_id
            GROUP BY
                cc.cohort_month,
                cm.order_month,
                months_since_first_order
        ),

        cohort_metrics AS (
            SELECT
                a.cohort_month,
                a.order_month,
                a.months_since_first_order,
                s.cohort_size,
                a.active_customers,
                SAFE_DIVIDE(a.active_customers, s.cohort_size) * 100
                    AS retention_rate
            FROM cohort_activity AS a
            INNER JOIN cohort_sizes AS s
                USING (cohort_month)
        )

        SELECT
            'kpi' AS section,
            CAST(NULL AS STRING) AS label,
            CAST(NULL AS STRING) AS secondary_label,
            unique_customers AS metric_count,
            total_orders AS metric_orders,
            repeat_customers,
            total_spending AS metric_value,
            SAFE_DIVIDE(repeat_customers, unique_customers) * 100
                AS repeat_rate,
            CAST(NULL AS FLOAT64) AS metric_value_2,
            CAST(NULL AS FLOAT64) AS metric_value_3,
            CAST(NULL AS FLOAT64) AS metric_value_4
        FROM kpis

        UNION ALL

        SELECT
            'state', state, CAST(NULL AS STRING),
            customer_count, CAST(NULL AS INT64),
            CAST(NULL AS INT64), CAST(NULL AS FLOAT64),
            CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64),
            CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64)
        FROM state_metrics

        UNION ALL

        SELECT
            'city', city, state,
            customer_count, CAST(NULL AS INT64),
            CAST(NULL AS INT64), CAST(NULL AS FLOAT64),
            CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64),
            CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64)
        FROM city_metrics

        UNION ALL

        SELECT
            'frequency', CAST(orders_per_customer AS STRING),
            CAST(NULL AS STRING), customer_count,
            CAST(NULL AS INT64), CAST(NULL AS INT64),
            CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64),
            CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64),
            CAST(NULL AS FLOAT64)
        FROM frequency_metrics

        UNION ALL

        SELECT
            'top_customer', customer_unique_id, CAST(NULL AS STRING),
            total_orders, total_orders, CAST(NULL AS INT64),
            total_spending, CAST(NULL AS FLOAT64),
            CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64),
            CAST(NULL AS FLOAT64)
        FROM top_customers

        UNION ALL

        SELECT
            'rfm', segment, CAST(NULL AS STRING),
            customer_count, CAST(NULL AS INT64),
            CAST(NULL AS INT64), CAST(NULL AS FLOAT64),
            CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64),
            CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64)
        FROM rfm_metrics

        UNION ALL

        SELECT
            'cohort',
            FORMAT_DATE('%Y-%m', cohort_month),
            CAST(months_since_first_order AS STRING),
            active_customers,
            cohort_size,
            CAST(NULL AS INT64),
            retention_rate,
            CAST(NULL AS FLOAT64),
            CAST(NULL AS FLOAT64),
            CAST(NULL AS FLOAT64),
            CAST(NULL AS FLOAT64)
        FROM cohort_metrics
    """

    rows = client.query(query, job_config=job_config(params)).result()

    data = {
        "kpis": {},
        "customers_by_state": [],
        "top_cities": [],
        "order_frequency": [],
        "top_customers": [],
        "rfm_segments": [],
        "cohort_retention": [],
    }

    for row in rows:
        if row.section == "kpi":
            customer_count = int(row.metric_count or 0)
            data["kpis"] = {
                "unique_customers": customer_count,
                "total_orders": int(row.metric_orders or 0),
                "repeat_customers": int(row.repeat_customers or 0),
                "repeat_customer_rate": round(
                    float(row.repeat_rate or 0), 2
                ),
                "average_customer_spending": round(
                    float(row.metric_value or 0) / max(customer_count, 1),
                    2,
                ),
            }

        elif row.section == "state":
            data["customers_by_state"].append({
                "state": row.label,
                "customer_count": int(row.metric_count or 0),
            })

        elif row.section == "city":
            data["top_cities"].append({
                "city": row.label,
                "state": row.secondary_label,
                "customer_count": int(row.metric_count or 0),
            })

        elif row.section == "frequency":
            data["order_frequency"].append({
                "orders_per_customer": int(row.label),
                "customer_count": int(row.metric_count or 0),
            })

        elif row.section == "top_customer":
            data["top_customers"].append({
                "customer_unique_id": row.label,
                "total_orders": int(row.metric_orders or 0),
                "total_spending": round(float(row.metric_value or 0), 2),
            })

        elif row.section == "rfm":
            data["rfm_segments"].append({
                "segment": row.label,
                "customer_count": int(row.metric_count or 0),
            })

        elif row.section == "cohort":
            data["cohort_retention"].append({
                "cohort_month": row.label,
                "months_since_first_order": int(row.secondary_label),
                "active_customers": int(row.metric_count or 0),
                "cohort_size": int(row.metric_orders or 0),
                "retention_rate": round(float(row.metric_value or 0), 2),
            })

    data["customers_by_state"].sort(
        key=lambda x: x["customer_count"], reverse=True
    )
    data["top_cities"] = sorted(
        data["top_cities"],
        key=lambda x: x["customer_count"],
        reverse=True,
    )
    data["order_frequency"].sort(
        key=lambda x: x["orders_per_customer"]
    )
    data["rfm_segments"].sort(
        key=lambda x: x["customer_count"], reverse=True
    )
    data["cohort_retention"].sort(
        key=lambda x: (x["cohort_month"], x["months_since_first_order"])
    )

    return data
