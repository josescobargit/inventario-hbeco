# Despliegue gratis

## Objetivo

Publicar el sistema sin gastar por ahora, manteniendo separadas sus partes:

- `frontend/` en Vercel.
- `backend/` en Render.
- Base de datos en Supabase.

## Como queda la arquitectura publicada

```text
Usuarios
  |
  v
Vercel (frontend)
  |
  v
Render (API FastAPI)
  |
  v
Supabase (PostgreSQL)
```

## Paso 1. Publicar backend en Render

Render sirve para dejar la API encendida en internet.

1. Entrar a [Render](https://render.com/) con GitHub.
2. Elegir `New +` -> `Blueprint`.
3. Seleccionar este repositorio.
4. Render detectara `render.yaml`.
5. Crear el servicio `inventario-operativo-api`.

### Variables obligatorias del backend

En Render, completar estas variables:

```text
ENVIRONMENT=production
COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=none
CORS_ORIGINS=["https://TU-FRONTEND.vercel.app"]
DATABASE_URL=postgresql+psycopg://postgres.PROJECT_REF:{password}@aws-0-REGION.pooler.supabase.com:5432/postgres?sslmode=require
MIGRATION_DATABASE_URL=postgresql+psycopg://postgres:{password}@db.PROJECT_REF.supabase.co:5432/postgres?sslmode=require
DATABASE_PASSWORD=TU_PASSWORD_REAL
```

### Aplicar la base

Cuando el backend ya exista en Render, correr migraciones desde tu equipo:

```bash
make db-schema
make db-seed
make db-check
```

Esto deja tablas, catalogo y comprobacion basica.

## Paso 2. Publicar frontend en Vercel

Vercel publicara solo la carpeta `frontend`.

1. Entrar a [Vercel](https://vercel.com/) con GitHub.
2. Elegir `Add New...` -> `Project`.
3. Importar este mismo repositorio.
4. En `Root Directory`, escoger `frontend`.
5. Antes de publicar, abrir [frontend/vercel.json](/Users/joseescobar/Documents/Codex/InventarioApp/frontend/vercel.json:1) y reemplazar `https://RENDER_BACKEND_URL` por la URL real del backend de Render.
6. Publicar.

### Para que sirve esa regla

El frontend usa `/api` como puerta unica hacia el backend. Vercel recibe esa ruta y la reenvia a Render. Asi:

- el navegador no queda amarrado a `127.0.0.1`
- no hay que editar JavaScript cada vez
- la sesion queda lista para trabajar con cookies

## Paso 3. Ajustar CORS con la URL final del frontend

Cuando Vercel te entregue la URL real, copiarla y actualizar en Render:

```text
CORS_ORIGINS=["https://TU-FRONTEND.vercel.app"]
```

Luego redeploy del backend.

## Paso 4. Primer ingreso

Al entrar al sistema por primera vez:

1. Crear usuario principal.
2. Ingresar con ese usuario.
3. Crear usuarios de `administracion`, `ventas`, `bodega` y `consulta`.
4. Cargar el stock fisico inicial.

## Por que Streamlit no cambia

La app nueva ya no depende de Streamlit. El archivo `app.py` sigue existiendo como sistema anterior, pero la operacion nueva vive en:

- [frontend/index.html](/Users/joseescobar/Documents/Codex/InventarioApp/frontend/index.html:1)
- [backend/app/main.py](/Users/joseescobar/Documents/Codex/InventarioApp/backend/app/main.py:1)

Si publicas Streamlit, veras la app vieja. Si publicas `frontend + backend`, veras el sistema nuevo.
