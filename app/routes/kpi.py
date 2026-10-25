import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.filters import Filters, get_filters
from app.schemas.kpi import KPIResponse
from app.schemas.monthly_sales import MonthlySalesItem
from app.services import kpi_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/kpi", response_model=KPIResponse)
def get_kpi(filters: Filters = Depends(get_filters)):
    try:
        return kpi_service.get_kpi(filters)
    except Exception:
        logger.exception("Failed to retrieve KPI data from BigQuery")
        raise HTTPException(
            status_code=500,
            detail="Gagal mengambil data KPI. Silakan coba lagi.",
        )


@router.get("/api/sales/monthly", response_model=list[MonthlySalesItem])
def get_monthly_sales(filters: Filters = Depends(get_filters)):
    try:
        return kpi_service.get_monthly_sales(filters)
    except Exception:
        logger.exception("Failed to retrieve monthly sales")
        raise HTTPException(
            status_code=500,
            detail="Gagal mengambil data penjualan bulanan.",
        )


@router.get("/api/overview/dashboard")
def get_overview_dashboard(filters: Filters = Depends(get_filters)):
    try:
        return kpi_service.get_overview_dashboard(filters)
    except Exception:
        logger.exception("Failed to retrieve overview dashboard")
        raise HTTPException(
            status_code=500,
            detail="Gagal mengambil data overview.",
        )


@router.get("/api/filters/options")
def get_filter_options():
    try:
        return kpi_service.get_filter_options()
    except Exception:
        logger.exception("Failed to retrieve filter options")
        raise HTTPException(
            status_code=500,
            detail="Gagal mengambil opsi filter.",
        )
