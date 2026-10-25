
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import kpi, products, customers, logistics

app = FastAPI()

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Olist Web App API is running"
    }


app.include_router(kpi.router)
app.include_router(products.router)
app.include_router(customers.router)
app.include_router(logistics.router)
