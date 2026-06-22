# Arquitectura del sistema

## Decision

El sistema nuevo se construira con:

- Frontend: HTML, CSS y JavaScript separados.
- Backend: FastAPI.
- Base de datos: PostgreSQL.
- App actual Streamlit: queda intacta como referencia hasta migrar funciones.

## Por que

Varias personas usaran el sistema desde distintos lugares. Para que todos vean el mismo inventario al mismo tiempo, necesitamos una base central y reglas aplicadas desde un backend.

## Estructura inicial

```text
backend/
  app/
    core/
    db/
    models/
    routers/
    schemas/
    services/
    parsers/
frontend/
  index.html
  css/
  js/
database/
docs/
```

## Principio de trabajo

Cada cambio debe explicar:

- Que se hara.
- Para que sirve.
- Por que se necesita.
- Como se verificara.
