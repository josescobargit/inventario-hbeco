# Ejemplos de API

## Iniciar sesion

Endpoint:

```text
POST /auth/login
```

```json
{
  "username": "ventas1",
  "password": "contrasena-del-usuario"
}
```

El backend crea una cookie de sesion protegida. El navegador la envia automaticamente en las siguientes operaciones y el backend toma ese usuario para permisos y auditoria.

## Registrar factura hecha en Contifico

Endpoint:

```text
POST /invoices
```

Ejemplo:

```json
{
  "invoice_number": "001-001-000000123",
  "customer_name": "TIA",
  "purchase_order_id": null,
  "contifico_source_id": null,
  "reason": "Factura registrada luego de confirmar disponibilidad",
  "notes": "Ejemplo inicial",
  "lines": [
    {
      "sku": "AE001",
      "quantity": 12
    },
    {
      "sku": "AR005",
      "quantity": 288
    }
  ]
}
```

## Que valida

- Que la factura no exista previamente.
- Que todos los SKU existan.
- Que haya disponible suficiente.

## Que actualiza

- Crea la factura.
- Crea las lineas de factura.
- Aumenta `facturado no despachado`.
- Registra movimiento de stock.
- Registra auditoria.

## Que NO hace

- No cambia `stock fisico confirmado`.
- No toma stock de Contifico.
- No marca despacho de bodega.

## Confirmar despacho de bodega

Endpoint:

```text
POST /dispatches
```

Ejemplo despacho completo:

```json
{
  "invoice_number": "001-001-000000123",
  "reason": "Bodega confirma despacho completo",
  "lines": [
    {
      "sku": "AE001",
      "dispatched_quantity": 12,
      "missing_quantity": 0
    }
  ]
}
```

Ejemplo despacho con faltante:

```json
{
  "invoice_number": "001-001-000000123",
  "reason": "Bodega indica que no encontro todo el producto",
  "lines": [
    {
      "sku": "AE001",
      "dispatched_quantity": 8,
      "missing_quantity": 4
    }
  ]
}
```

## Que hace el despacho

- Si hay cantidad despachada, baja `stock fisico confirmado`.
- La cantidad reportada deja de estar en `facturado no despachado`.
- Si hay faltante, se mueve a `stock bloqueado por incidencia`.
- Si hay faltante, crea una incidencia ligada a la factura y al producto.
- Actualiza el estado de la factura.

## Crear reserva

Endpoint:

```text
POST /reservations
```

Ejemplo:

```json
{
  "sku": "AE001",
  "quantity": 24,
  "customer_name": "FAVORITA",
  "purchase_order_id": null,
  "reason": "Separar producto para OC pendiente de facturar"
}
```

## Eliminar reserva manualmente

Endpoint:

```text
POST /reservations/{reservation_id}/release
```

Ejemplo:

```json
{
  "reason": "OC cancelada por el cliente"
}
```

## Que hace una reserva

- Aumenta `reserved`.
- Baja el disponible para facturar.
- Exige motivo.
- Deja movimiento y auditoria.
- No tiene vencimiento automatico.

## Solicitar ajuste de stock fisico

Endpoint:

```text
POST /stock-adjustments
```

Ejemplo:

```json
{
  "sku": "AE001",
  "requested_physical_confirmed": 120,
  "reason": "Conteo fisico semanal indica 120 unidades en bodega"
}
```

## Aprobar ajuste

Endpoint:

```text
POST /stock-adjustments/{approval_id}/approve
```

Ejemplo:

```json
{
  "reason": "Admin reviso conteo y aprueba ajuste"
}
```

## Rechazar ajuste

Endpoint:

```text
POST /stock-adjustments/{approval_id}/reject
```

Ejemplo:

```json
{
  "reason": "Conteo no coincide con factura pendiente de despacho"
}
```

## Que hace un ajuste de stock

- La solicitud no cambia inventario todavia.
- La aprobacion cambia `stock fisico confirmado`.
- La aprobacion deja movimiento de stock con antes y despues.
- El rechazo no cambia inventario.
- Toda decision exige motivo y queda en auditoria.
- No borra reservas, facturas pendientes ni incidencias.

## Plantilla y vista previa de conteo masivo

```text
GET /stock-imports/template
POST /stock-imports/preview
```

La vista previa recibe un archivo `.csv` o `.xlsx` como `multipart/form-data`. Valida que esten todos los productos y devuelve las diferencias sin modificar inventario.

## Solicitar conteo masivo

```text
POST /stock-imports
```

```json
{
  "reason": "Conteo fisico inicial completo",
  "lines": [
    {"sku": "AE001", "physical_confirmed": 120},
    {"sku": "AE002", "physical_confirmed": 96}
  ]
}
```

El ejemplo es abreviado; la solicitud real debe contener todos los productos activos.

## Aprobar o rechazar conteo masivo

```text
GET /stock-imports
POST /stock-imports/{approval_id}/approve
POST /stock-imports/{approval_id}/reject
```

La decision exige motivo. La aprobacion actualiza todo el conteo en una transaccion y genera movimientos y auditoria por producto.

## Crear usuario

Solo el rol principal puede ejecutar:

```text
POST /users
```

```json
{
  "username": "bodega1",
  "email": "bodega@empresa.com",
  "full_name": "Responsable de bodega",
  "temporary_password": "provisional-segura-123",
  "role": "bodega",
  "reason": "Acceso aprobado para despachos y conteos"
}
```

## Cambiar rol o estado

```text
PATCH /users/{user_id}
```

```json
{
  "role": "consulta",
  "is_active": true,
  "reason": "Cambio de responsabilidad"
}
```

## Cambiar la propia contrasena

```text
POST /auth/change-password
```

```json
{
  "current_password": "provisional-segura-123",
  "new_password": "contrasena-definitiva-456",
  "reason": "Cambio obligatorio de contrasena provisional"
}
```

El cambio cierra todas las sesiones del usuario. Debe ingresar nuevamente con la nueva contrasena.

## Restablecer contrasena

Solo el principal puede ejecutar:

```text
POST /users/{user_id}/reset-password
```

```json
{
  "temporary_password": "nueva-provisional-789",
  "reason": "El usuario olvido su contrasena"
}
```

El restablecimiento cierra las sesiones existentes y obliga al usuario a cambiar la clave provisional.
