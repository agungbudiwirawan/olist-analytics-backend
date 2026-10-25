
from pydantic import BaseModel


class KPIResponse(BaseModel):
    total_sales: float
    total_orders: int
    total_items: int
    total_freight: float
