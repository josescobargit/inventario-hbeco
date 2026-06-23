# Esquema SQL historico

Esta carpeta conserva el esquema SQL con el que comenzo el proyecto.

## Archivo actual

```text
001_initial_schema.sql
```

## Importante

Este archivo ya no es la fuente activa del esquema y no debe editarse para cambios nuevos. Las migraciones versionadas viven en:

```text
database/migrations/
```

Para actualizar una base se usa `make db-schema`.
