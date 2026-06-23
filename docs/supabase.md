# Supabase

## Enfoque

Supabase se usa como PostgreSQL administrado. FastAPI conserva las reglas de negocio, permisos y sesiones de la aplicacion; Alembic sigue siendo la unica fuente de cambios estructurales.

Las credenciales de PostgreSQL pertenecen exclusivamente al backend. Nunca deben copiarse al JavaScript del frontend ni guardarse en Git.

El backend limita a 10 segundos la apertura de una conexion y a 15 segundos la espera del pool. Si Supabase esta pausado o inaccesible, la operacion falla de forma controlada en lugar de dejar la pantalla esperando indefinidamente.

## Crear las conexiones

En el proyecto de Supabase, abrir `Connect` y copiar estas dos conexiones:

1. `Session pooler`, puerto 5432, para el trafico habitual de FastAPI.
2. `Direct connection`, puerto 5432, para migraciones y tareas administrativas.

SQLAlchemy con Psycopg necesita el prefijo `postgresql+psycopg://`. Tambien se exige SSL.

Crear `.env` desde `.env.example` y configurar:

```env
ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://postgres.PROJECT_REF:{password}@aws-0-REGION.pooler.supabase.com:5432/postgres?sslmode=require
MIGRATION_DATABASE_URL=postgresql+psycopg://postgres:{password}@db.PROJECT_REF.supabase.co:5432/postgres?sslmode=require
DATABASE_PASSWORD=PASSWORD
COOKIE_SECURE=true
```

Para no repetir ni codificar manualmente la clave, se recomienda escribir `{password}` en ambas URLs y guardar el valor real solo en `DATABASE_PASSWORD`. La aplicacion lo codifica de forma segura antes de conectarse.

La conexion directa requiere IPv6 salvo que el proyecto tenga el complemento IPv4. Si el equipo o el proveedor solo tiene IPv4, se puede usar temporalmente la URL del `Session pooler` en ambas variables.

## Preparar la base

Con `.env` configurado:

```bash
make db-schema
make db-current
make db-seed
make db-check
```

`db-schema` aplica las migraciones pendientes. `db-seed` carga el catalogo sin tomar el stock de Contifico. `db-check` comprueba la conexion, cuenta productos y muestra el espacio ocupado.

## Espacio disponible

El plan gratuito permite una base de datos de 500 MB. Al superar el limite, Supabase puede poner el proyecto en modo de solo lectura.

Los archivos actuales del proyecto contienen 29 productos, 9 movimientos historicos y aproximadamente 5.7 KB de datos CSV. Existe margen suficiente para comenzar y operar durante bastante tiempo, aunque el crecimiento real dependera del volumen de movimientos y auditorias.

Conviene ejecutar periodicamente:

```bash
make db-check
```

Los documentos, imagenes y archivos de ordenes no deben guardarse como binarios dentro de PostgreSQL. Si se necesitan, se almacenan en Supabase Storage y en la base solo se conserva su ruta y metadata.

## Rutina para cambios futuros

```bash
make db-revision MESSAGE="descripcion breve"
make db-validate
make test
make db-schema
```

Una migracion ya aplicada no se modifica; cualquier ajuste posterior se entrega como una migracion nueva.

## Referencias oficiales

- [Conexiones directas y poolers](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Tamano de base de datos y modo de solo lectura](https://supabase.com/docs/guides/platform/database-size)
- [Planes y limites](https://supabase.com/pricing)
