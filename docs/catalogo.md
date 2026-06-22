# Catalogo de productos

## Fuente

La fuente inicial del catalogo es el Excel exportado desde Contifico:

```text
/Users/joseescobar/Downloads/PRODUCTOS HOME .xlsx
```

Del Excel se toman estos datos:

- SKU.
- Nombre.
- Descripcion.
- Categoria.
- Codigo de barras/catalogo.
- Codigo auxiliar de Contifico.
- Costo.
- Unidades por caja.

## Dato que NO se toma

El stock de Contifico no se copia al sistema operativo.

Motivo: Contifico sirve como referencia para catalogo, Kardex, facturas y comparaciones, pero el stock operativo debe venir de stock fisico confirmado y flujo interno del sistema.

## Regla UXC

UXC significa unidades por caja.

Regla confirmada:

- Sachets/ristras: 288 unidades por caja.
- Packs: 6 unidades por caja.
- Todo lo demas: 12 unidades por caja.

## Archivo generado

La semilla limpia queda en:

```text
database/seed_data/products_seed.csv
```

## Como regenerarlo

```bash
python backend/scripts/build_product_seed.py \
  --input "/Users/joseescobar/Downloads/PRODUCTOS HOME .xlsx" \
  --output database/seed_data/products_seed.csv
```

## Validacion actual

La semilla actual tiene:

- 29 productos.
- 21 productos con UXC 12.
- 6 productos con UXC 6.
- 2 productos con UXC 288.
