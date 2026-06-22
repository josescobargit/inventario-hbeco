# Reglas de negocio

## Disponibilidad

Formula confirmada:

```text
Disponible para facturar =
Stock fisico confirmado
- Reservado
- Facturado no despachado
- Stock bloqueado por incidencia
```

## Facturacion

- Si no hay stock suficiente, el sistema bloquea la facturacion.
- La factura se hace en Contifico.
- Luego se registra o importa en el sistema con confirmacion.
- Al confirmar, se descuenta del inventario operativo.
- En la base, una factura confirmada aumenta `facturado no despachado`; no cambia el stock fisico confirmado hasta que bodega confirme o exista un ajuste aprobado.

## Despacho

- Bodega debe poder confirmar despacho completo.
- Bodega debe poder confirmar despacho parcial.
- Bodega debe poder marcar no despachado y explicar por que.
- Lo despachado baja el stock fisico confirmado.
- Lo faltante se bloquea como incidencia para que no vuelva a aparecer disponible.

## Incidencias

Una incidencia se abre cuando:

- Bodega dice que no hay producto despues de facturar.
- Hay error de despacho.
- Hay devolucion.
- No llego producto a piso.
- Contifico, bodega y sistema no cuadran.

## Reservas

- Una reserva separa stock para una OC, cliente o pedido pendiente.
- Una reserva baja el disponible para facturar.
- Las reservas no vencen automaticamente.
- Una reserva puede eliminarse manualmente con confirmacion y motivo.
- Eliminar una reserva devuelve esa cantidad al disponible.

## Ajustes de stock fisico

- Bodega puede solicitar un ajuste cuando el conteo fisico no coincide con el sistema.
- Solicitar un ajuste no cambia el inventario.
- Un admin debe aprobar o rechazar el ajuste.
- Si se aprueba, cambia solo `stock fisico confirmado`.
- Si se rechaza, no cambia nada del inventario.
- Toda solicitud, aprobacion o rechazo exige motivo.
- Todo queda con trazabilidad: usuario, fecha, antes, despues y motivo.
- El ajuste no borra reservas, facturas pendientes ni incidencias; esas cantidades siguen visibles para no esconder problemas.

## Catalogo

- El Excel de Contifico es fuente del catalogo.
- Se toman datos importantes: SKU, nombre, descripcion, codigo de barras/catalogo, costo.
- No se toma el stock de Contifico como stock operativo.

## Unidades por caja

- Sachets: 288 unidades por caja.
- Packs: 6 unidades por caja.
- Todo lo demas: 12 unidades por caja.

## Usuarios y autorizaciones

- Principal administra usuarios y aprueba ajustes de stock.
- Administracion y ventas pueden reservar y registrar facturas.
- Bodega confirma despachos y solicita ajustes de conteo.
- Consulta solo puede revisar inventario.
- Toda operacion protegida usa el usuario identificado por el backend para la auditoria.
