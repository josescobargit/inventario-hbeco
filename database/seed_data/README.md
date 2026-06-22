# Seed data

Esta carpeta guarda datos iniciales limpios para cargar en PostgreSQL.

## Productos

`products_seed.csv` se genera desde el Excel de Contifico:

```bash
python backend/scripts/build_product_seed.py \
  --input "/Users/joseescobar/Downloads/PRODUCTOS HOME .xlsx" \
  --output database/seed_data/products_seed.csv
```

## Regla importante

El stock de Contifico no se copia a esta semilla. El sistema operativo parte de stock fisico confirmado por bodega/conteo.

## Cargar a PostgreSQL

Cuando la base ya exista y `DATABASE_URL` apunte a PostgreSQL:

```bash
python backend/scripts/load_product_seed.py --input database/seed_data/products_seed.csv
```

Este cargador crea los productos y deja su posicion inicial de stock operativo en cero. El stock real se cargara luego desde conteo fisico confirmado.
