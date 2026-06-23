# InventarioApp

Sistema de inventario operativo para controlar disponibilidad real, facturacion, reservas, despacho e incidencias.

## Estado actual

La app Streamlit existente sigue intacta:

- `app.py`
- `storage.py`
- `order_parsers.py`

La nueva arquitectura multiusuario empieza en carpetas separadas:

- `backend/`: API FastAPI y reglas de negocio.
- `frontend/`: pantallas HTML, CSS y JavaScript.
- `database/`: notas y futura configuracion de PostgreSQL/migraciones.
- `docs/`: arquitectura, reglas y documentos de plan.

## Decision tecnica

Base final: PostgreSQL.

Motivo: varias personas usaran el sistema desde distintos lugares y deben ver el mismo inventario al mismo tiempo.

## Formula de disponibilidad

```text
Disponible para facturar =
Stock fisico confirmado
- Reservado
- Facturado no despachado
- Stock bloqueado por incidencia
```

## Usuarios y roles

La API ya controla permisos para principal, administracion, ventas, bodega y consulta. Los usuarios ingresan con una cuenta interna y contrasena. La matriz y el proceso para crear el primer usuario estan en:

```text
docs/usuarios_roles.md
```

Las contrasenas se guardan como huellas criptograficas, las sesiones usan cookies protegidas y las claves provisionales deben cambiarse antes de operar.

## Catalogo inicial

Ya existe una semilla limpia en:

```text
database/seed_data/products_seed.csv
```

El proceso esta documentado en:

```text
docs/catalogo.md
```

## Esquema de PostgreSQL

El esquema se administra con migraciones versionadas de Alembic:

```text
database/migrations/
```

`make db-schema` aplica las revisiones pendientes y `make db-current` muestra la revision instalada.

## Desarrollo local

Los pasos para levantar PostgreSQL, cargar el catalogo y correr backend/frontend estan en:

```text
docs/desarrollo_local.md
```

Para usar Supabase como PostgreSQL administrado, consultar:

```text
docs/supabase.md
```

## Ejemplos de API

```text
docs/api_ejemplos.md
```

## Carga inicial de stock

La carga completa desde CSV o Excel, su validacion y aprobacion estan documentadas en:

```text
docs/carga_stock_fisico.md
```
