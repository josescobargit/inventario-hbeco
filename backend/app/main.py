from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import authentication, dispatches, health, invoices, products, reservations, stock_adjustments, users


settings = get_settings()
app = FastAPI(
    title="Inventario Operativo API",
    description="API central para inventario, facturacion, reservas, despacho e incidencias.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(authentication.router)
app.include_router(products.router)
app.include_router(invoices.router)
app.include_router(dispatches.router)
app.include_router(reservations.router)
app.include_router(stock_adjustments.router)
app.include_router(users.router)
