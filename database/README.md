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

## Siguiente paso

Crear migraciones formales cuando confirmemos la primera version del modelo.

El esquema SQL inicial esta en:

```text
database/schema/001_initial_schema.sql
```

## Semilla de productos

La semilla inicial del catalogo vive en:

```text
database/seed_data/products_seed.csv
```

Se genera desde el Excel de Contifico sin copiar stock.
