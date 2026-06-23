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

## 3. Aplicar migraciones

```bash
make db-schema
```

Este comando lleva la base hasta la ultima revision de Alembic. Puede ejecutarse varias veces de forma segura.

Comprobar la revision instalada:

```bash
make db-current
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

## Crear cambios de base de datos

Primero se modifican los modelos de SQLAlchemy. Despues se genera una nueva migracion:

```bash
make db-revision MESSAGE="agregar campo de ejemplo"
```

Antes de compartirla se revisa el archivo generado y se valida que el historial completo produzca SQL correcto:

```bash
make db-validate
make test
```

Nunca se modifica una migracion que ya fue aplicada en una base compartida; se crea una nueva.
