import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.filters import Filters, get_filters
from app.services import customers_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/customers/dashboard")
def get_customer_dashboard(filters: Filters = Depends(get_filters)):
    try:
        return customers_service.get_customer_dashboard(filters)
    except Exception:
        logger.exception("Failed to retrieve customer dashboard")
        raise HTTPException(
            status_code=500,
            detail="Gagal mengambil data customer.",
        )
