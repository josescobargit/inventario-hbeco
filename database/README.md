# Database

La base final sera PostgreSQL.

## Regla importante

El stock de Contifico no se toma como stock operativo real. Contifico sera referencia para catalogo, facturas, Kardex y comparaciones.

## Formula confirmada

```text
Disponible para facturar =
Stock fisico confirmado
- Reservado
- Facturado no despachado
- Stock bloqueado por incidencia
```

## Migraciones

Alembic es la unica via activa para crear o modificar el esquema. La configuracion vive en:

```text
alembic.ini
database/migrations/
```

Aplicar todas las migraciones pendientes:

```bash
make db-schema
```

Consultar la version aplicada:

```bash
make db-current
```

Crear una migracion despues de modificar los modelos:

```bash
make db-revision MESSAGE="descripcion breve"
```

El archivo `database/schema/001_initial_schema.sql` queda congelado como referencia historica. No debe usarse para cambios nuevos.

La configuracion con conexiones separadas para Supabase esta documentada en `docs/supabase.md`.

## Semilla de productos

La semilla inicial del catalogo vive en:

```text
database/seed_data/products_seed.csv
```

Se genera desde el Excel de Contifico sin copiar stock.
