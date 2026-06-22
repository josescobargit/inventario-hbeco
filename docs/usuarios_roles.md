# Usuarios y roles

## Objetivo

Cada operacion debe quedar ligada al usuario real que la ejecuto. El navegador no puede indicar dentro de una factura, reserva, despacho o ajuste que la accion fue realizada por otra persona.

## Matriz provisional

| Rol | Ver inventario | Facturar | Reservar | Despachar | Solicitar ajuste | Aprobar ajuste | Administrar usuarios |
|---|---:|---:|---:|---:|---:|---:|---:|
| Principal | Si | Si | Si | Si | Si | Si | Si |
| Administracion | Si | Si | Si | No | No | No | No |
| Ventas | Si | Si | Si | No | No | No | No |
| Bodega | Si | No | No | Si | Si | No | No |
| Consulta | Si | No | No | No | No | No | No |

`Principal` representa al administrador general. Es el unico que aprueba cambios de stock y administra accesos en esta version.

## Primer usuario

Cuando la tabla de usuarios esta vacia se crea una sola vez el principal inicial:

```http
POST /users/bootstrap
Content-Type: application/json
```

```json
{
  "username": "principal",
  "email": "principal@empresa.com",
  "full_name": "Usuario principal",
  "password": "una-contrasena-inicial-segura",
  "reason": "Configuracion inicial del sistema"
}
```

Despues de crear el primer usuario, ese endpoint queda cerrado.

## Inicio de sesion interno

Cada persona ingresa con el usuario y la contrasena creados dentro del sistema. No se usa Google, Microsoft ni otro proveedor externo.

Cuando el principal crea una cuenta, asigna una contrasena provisional. El nuevo usuario puede entrar con ella, pero no puede facturar, reservar, despachar ni ajustar inventario hasta reemplazarla por su propia contrasena.

La contrasena no se guarda como texto legible. Se transforma en una huella criptografica que permite comprobarla sin conocer la original.

La sesion dura 12 horas y se guarda en una cookie protegida. Cerrar sesion, cambiar la contrasena, desactivar el usuario o restablecer su clave revoca las sesiones correspondientes.

Despues de 5 intentos incorrectos, la cuenta queda bloqueada durante 15 minutos.

## Reglas de seguridad ya aplicadas

- Un usuario inactivo no puede operar.
- Una ruta sin usuario responde `401`.
- Una accion no permitida por el rol responde `403`.
- Una contrasena provisional bloquea las operaciones hasta que sea cambiada.
- El ID de auditoria nace en el backend, no en el formulario enviado.
- Los usuarios no se borran: se desactivan para conservar el historial.
- Siempre debe quedar al menos un principal activo.
- Crear o modificar usuarios exige motivo y genera auditoria.
- Restablecer una contrasena exige motivo y obliga a cambiarla en el siguiente ingreso.
