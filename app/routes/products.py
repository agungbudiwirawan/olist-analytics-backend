import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.filters import Filters, get_filters
from app.services import products_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/products/categories")
def get_product_categories(filters: Filters = Depends(get_filters)):
    try:
        return products_service.get_product_categories(filters)
    except Exception:
        logger.exception("Failed to retrieve product categories")
        raise HTTPException(
            status_code=500,
            detail="Gagal mengambil data kategori produk.",
        )
