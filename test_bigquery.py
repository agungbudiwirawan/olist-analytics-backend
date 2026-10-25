
from google.cloud import bigquery

client = bigquery.Client(project="angelic-digit-481505-r7")

query = """
SELECT
    SUM(total_item_value) AS total_sales,
    COUNT(DISTINCT order_id) AS total_orders,
    COUNT(*) AS total_items,
    SUM(freight_value) AS total_freight
FROM `angelic-digit-481505-r7.olist_analytics.fact_order_items`
"""

result = client.query(query).result()

for row in result:
    print(dict(row.items()))
