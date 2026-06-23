# Carga masiva de stock fisico

## Objetivo

Cargar el conteo completo de bodega para los 29 productos sin modificar el inventario antes de una revision.

## Archivo permitido

El sistema acepta `.csv` y `.xlsx`, con un maximo de 5 MB. La plantilla se descarga desde el modulo `Ajustes` y contiene:

```text
SKU,Producto,Stock_Fisico
AE001,Shampoo Ana Elixir Romero 370 ML.,0
```

`Stock_Fisico` siempre se expresa en unidades exactas, no en cajas. La pantalla sigue mostrando las unidades por caja para ayudar a interpretar el conteo.

## Validaciones

- Deben aparecer todos los productos activos del catalogo.
- No puede haber SKU desconocidos o duplicados.
- El conteo debe ser un entero mayor o igual a cero.
- Un archivo incompleto puede revisarse, pero no enviarse.
- Solo puede existir un conteo masivo pendiente de decision.

## Flujo

1. Bodega o el principal descarga la plantilla.
2. Bodega escribe las unidades fisicas contadas.
3. Se carga el archivo y el sistema muestra stock actual, conteo y diferencia.
4. La confirmacion crea una solicitud; todavia no cambia stock.
5. El principal revisa el documento y aprueba o rechaza con motivo.
6. Al aprobar, todos los productos cambian dentro de una sola transaccion.

Si cualquier stock cambia mientras la solicitud espera aprobacion, el sistema bloquea la aplicacion completa y exige cargar un conteo actualizado.

## Auditoria

La solicitud, decision y cada producto modificado registran usuario, fecha, motivo, valor anterior, valor nuevo y documento de aprobacion.
