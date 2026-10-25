import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.filters import Filters, get_filters
from app.services import logistics_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/logistics/dashboard")
def get_logistics_dashboard(filters: Filters = Depends(get_filters)):
    try:
        return logistics_service.get_logistics_dashboard(filters)
    except Exception:
        logger.exception("Failed to retrieve logistics dashboard")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve logistics analytics from BigQuery.",
        )
