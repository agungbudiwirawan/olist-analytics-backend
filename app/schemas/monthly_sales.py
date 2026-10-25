
from pydantic import BaseModel


class MonthlySalesItem(BaseModel):
    month: str
    total_sales: float
    total_orders: int
