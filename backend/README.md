# Backend - Inventario Operativo

Este backend sera el cerebro del sistema nuevo.

## Que hace

- Expone una API con FastAPI.
- Valida reglas de inventario.
- Guarda movimientos, facturas, reservas, despachos e incidencias.
- Se conectara a PostgreSQL como base central.

## Por que existe

La app actual en Streamlit funciona como prototipo operativo, pero mezcla pantallas, reglas y datos. Para multiples usuarios desde distintos lugares necesitamos un backend central que aplique siempre las mismas reglas.

## Primer comando local

Cuando las dependencias esten instaladas y PostgreSQL este levantado:

```bash
uvicorn app.main:app --reload --app-dir backend
```

La API deberia responder en:

```text
http://127.0.0.1:8000/health
```

Tambien quedaran disponibles:

```text
http://127.0.0.1:8000/products
http://127.0.0.1:8000/products/availability
http://127.0.0.1:8000/invoices
http://127.0.0.1:8000/dispatches
http://127.0.0.1:8000/reservations
http://127.0.0.1:8000/stock-adjustments
```
