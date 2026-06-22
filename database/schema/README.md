# Schema

Esta carpeta contiene el esquema inicial de PostgreSQL.

## Archivo actual

```text
001_initial_schema.sql
```

## Como usarlo mas adelante

Cuando PostgreSQL este creado:

```bash
psql "$DATABASE_URL" -f database/schema/001_initial_schema.sql
```

Este archivo es una base inicial. Cuando instalemos Alembic, estas definiciones se convertiran en migraciones versionadas.
