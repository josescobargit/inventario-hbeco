# Desarrollo local

## Objetivo

Levantar PostgreSQL, aplicar el esquema, cargar el catalogo y ejecutar backend/frontend en local.

## Requisito

Python 3.9 o superior.

Instalar Docker Desktop o tener Docker disponible en terminal.

Validar:

```bash
docker --version
docker compose version
```

Crear el entorno Python e instalar solo las dependencias del backend:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

Ejecutar pruebas:

```bash
make test
```

## 1. Levantar PostgreSQL

```bash
make db-up
```

Esto crea una base local:

```text
postgresql+psycopg://inventario:inventario@localhost:5432/inventario
```

## 2. Configurar variables

Copiar `.env.example` a `.env`:

```bash
cp .env.example .env
```

## 3. Aplicar esquema

```bash
make db-schema
```

## 4. Cargar productos

```bash
make db-seed
```

Esto carga productos y crea posiciones iniciales de stock en cero.

## 5. Verificar base

```bash
PYTHONPATH=backend python backend/scripts/check_db.py
```

## 6. Levantar backend

```bash
make backend
```

API:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/products
http://127.0.0.1:8000/products/availability
http://127.0.0.1:8000/invoices
http://127.0.0.1:8000/dispatches
http://127.0.0.1:8000/reservations
http://127.0.0.1:8000/stock-adjustments
http://127.0.0.1:8000/users
```

Antes de usar rutas protegidas se crea el primer principal desde la pantalla o con `POST /users/bootstrap`. Luego se inicia sesion con `POST /auth/login`; el navegador conserva la sesion en una cookie protegida. Ver `docs/usuarios_roles.md`.

## 7. Levantar frontend

```bash
make frontend
```

Pantalla:

```text
http://127.0.0.1:5173
```
