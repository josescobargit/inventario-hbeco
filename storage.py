import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd


INVENTORY_COLUMNS = [
    "SKU",
    "Producto",
    "Físico",
    "Por Recibir",
    "Reservado",
    "Min_Alert",
    "Nota_Alerta",
    "Costo",
]

DB_PATH = os.getenv("INVENTARIO_DB_PATH", "inventario.sqlite3")
STORAGE_BACKEND = os.getenv("INVENTARIO_STORAGE", "sqlite").lower()
APP_TIMEZONE = os.getenv("INVENTARIO_TIMEZONE", "America/Guayaquil")
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DISPLAY_DATETIME_FORMAT = "%d/%m/%Y %H:%M"


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _timezone():
    try:
        return ZoneInfo(APP_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def now_text():
    return datetime.now(_timezone()).strftime(DATETIME_FORMAT)


def now_display():
    return datetime.now(_timezone()).strftime(DISPLAY_DATETIME_FORMAT)


def timezone_label():
    return APP_TIMEZONE


def format_datetime_series(series):
    parsed = pd.to_datetime(series, errors="coerce")
    return parsed.dt.strftime(DISPLAY_DATETIME_FORMAT).fillna(series)


def _empty_inventory(catalog):
    return pd.DataFrame(
        [
            {
                "SKU": sku,
                "Producto": product,
                "Físico": 0,
                "Por Recibir": 0,
                "Reservado": 0,
                "Min_Alert": 10,
                "Nota_Alerta": "",
                "Costo": 0.0,
            }
            for sku, product in catalog.items()
        ]
    )


def normalize_inventory(df, catalog):
    if df is None or df.empty:
        df = _empty_inventory(catalog)
    else:
        df = df.copy()

    if "Tránsito" in df.columns:
        df.rename(columns={"Tránsito": "Por Recibir"}, inplace=True)
    if "Llegando a Bodega" in df.columns and "Por Recibir" not in df.columns:
        df.rename(columns={"Llegando a Bodega": "Por Recibir"}, inplace=True)
    if "Comprometido" in df.columns and "Reservado" not in df.columns:
        df.rename(columns={"Comprometido": "Reservado"}, inplace=True)

    for col in INVENTORY_COLUMNS:
        if col not in df.columns:
            if col == "Producto":
                df[col] = df["SKU"].map(catalog).fillna("Producto no catalogado")
            elif col == "Min_Alert":
                df[col] = 10
            elif col == "Costo":
                df[col] = 0.0
            elif col == "Nota_Alerta":
                df[col] = ""
            else:
                df[col] = 0

    known = set(df["SKU"].astype(str))
    missing = [
        {
            "SKU": sku,
            "Producto": product,
            "Físico": 0,
            "Por Recibir": 0,
            "Reservado": 0,
            "Min_Alert": 10,
            "Nota_Alerta": "",
            "Costo": 0.0,
        }
        for sku, product in catalog.items()
        if sku not in known
    ]
    if missing:
        df = pd.concat([df, pd.DataFrame(missing)], ignore_index=True)

    df["SKU"] = df["SKU"].astype(str).str.upper().str.strip()
    df["Producto"] = df["Producto"].fillna(df["SKU"].map(catalog)).fillna("").astype(str)
    df["Nota_Alerta"] = df["Nota_Alerta"].fillna("").astype(str)

    for col in ["Físico", "Por Recibir", "Reservado", "Min_Alert"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df["Costo"] = pd.to_numeric(df["Costo"], errors="coerce").fillna(0.0)

    return df[INVENTORY_COLUMNS].sort_values("SKU").reset_index(drop=True)


def _init_sqlite():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                SKU TEXT PRIMARY KEY,
                Producto TEXT NOT NULL,
                Fisico INTEGER NOT NULL DEFAULT 0,
                LlegandoBodega INTEGER NOT NULL DEFAULT 0,
                Comprometido INTEGER NOT NULL DEFAULT 0,
                Reservado INTEGER NOT NULL DEFAULT 0,
                MinAlert INTEGER NOT NULL DEFAULT 10,
                NotaAlerta TEXT NOT NULL DEFAULT '',
                Costo REAL NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS movement_history (
                Fecha TEXT NOT NULL,
                SKU TEXT NOT NULL,
                Tipo TEXT NOT NULL,
                Cantidad REAL NOT NULL,
                Nota TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sales_history (
                Fecha TEXT NOT NULL,
                SKU TEXT NOT NULL,
                Producto TEXT NOT NULL,
                Cantidad REAL NOT NULL,
                Referencia TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS invoice_lines (
                Fecha TEXT NOT NULL,
                NumeroFactura TEXT NOT NULL,
                Cliente TEXT,
                OC TEXT,
                Usuario TEXT,
                SKU TEXT NOT NULL,
                Producto TEXT NOT NULL,
                Cantidad REAL NOT NULL,
                Estado TEXT NOT NULL DEFAULT 'Activa',
                Nota TEXT,
                FechaAnulacion TEXT,
                UsuarioAnulacion TEXT,
                MotivoAnulacion TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conciliation_history (
                Fecha_Conciliacion TEXT NOT NULL,
                SKU TEXT NOT NULL,
                Producto TEXT NOT NULL,
                Stock_Contifico REAL NOT NULL,
                Fisico_Real REAL NOT NULL,
                Diferencia REAL NOT NULL
            )
            """
        )
        _ensure_inventory_schema(conn)


def _ensure_inventory_schema(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(inventory)").fetchall()}
    if "Reservado" not in columns:
        conn.execute("ALTER TABLE inventory ADD COLUMN Reservado INTEGER NOT NULL DEFAULT 0")
        if "Comprometido" in columns:
            conn.execute("UPDATE inventory SET Reservado = Comprometido")


def _inventory_to_sql_columns(df):
    return df.rename(
        columns={
            "Físico": "Fisico",
            "Por Recibir": "LlegandoBodega",
            "Min_Alert": "MinAlert",
            "Nota_Alerta": "NotaAlerta",
        }
    )


def _inventory_from_sql_columns(df):
    return df.rename(
        columns={
            "Fisico": "Físico",
            "LlegandoBodega": "Por Recibir",
            "MinAlert": "Min_Alert",
            "NotaAlerta": "Nota_Alerta",
        }
    )


def _seed_table_from_csv_if_empty(conn, table, csv_path, columns):
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    if count > 0 or not os.path.exists(csv_path):
        return

    seed_df = pd.read_csv(csv_path)
    for col in columns:
        if col not in seed_df.columns:
            seed_df[col] = ""
    seed_df[columns].to_sql(table, conn, if_exists="append", index=False)


def load_inventory(catalog, csv_path="inventario_data.csv"):
    if STORAGE_BACKEND == "csv":
        if os.path.exists(csv_path):
            return normalize_inventory(pd.read_csv(csv_path), catalog)
        return _empty_inventory(catalog)

    _init_sqlite()
    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
    if count == 0:
        seed = pd.read_csv(csv_path) if os.path.exists(csv_path) else _empty_inventory(catalog)
        save_inventory(normalize_inventory(seed, catalog), csv_path=csv_path)
    with _connect() as conn:
        df = pd.read_sql_query("SELECT * FROM inventory", conn)

    return normalize_inventory(_inventory_from_sql_columns(df), catalog)


def save_inventory(df, csv_path="inventario_data.csv"):
    clean_df = normalize_inventory(df, {})
    if STORAGE_BACKEND == "csv":
        clean_df.to_csv(csv_path, index=False)
        return

    _init_sqlite()
    sql_df = _inventory_to_sql_columns(clean_df)
    with _connect() as conn:
        conn.execute("DELETE FROM inventory")
        sql_df.to_sql("inventory", conn, if_exists="append", index=False)


def adjust_stock(deltas, csv_path="inventario_data.csv"):
    """Aplica cambios incrementales al stock Físico de forma atómica.

    deltas: dict {SKU: cantidad} (positivo suma, negativo resta).
    No deja el Físico por debajo de 0. Solo toca los SKU indicados,
    así dos usuarios que modifican productos distintos no se pisan
    (a diferencia de save_inventory, que reescribe toda la tabla).
    Devuelve {SKU: nuevo_fisico}.
    """
    deltas = {str(k).upper().strip(): int(v) for k, v in deltas.items() if int(v) != 0}
    if not deltas:
        return {}

    if STORAGE_BACKEND == "csv":
        base = pd.read_csv(csv_path) if os.path.exists(csv_path) else _empty_inventory({})
        df = normalize_inventory(base, {})
        for sku, delta in deltas.items():
            mask = df["SKU"] == sku
            if mask.any():
                actual = int(df.loc[mask, "Físico"].iloc[0])
                df.loc[mask, "Físico"] = max(0, actual + delta)
        df.to_csv(csv_path, index=False)
        return {sku: int(df.loc[df["SKU"] == sku, "Físico"].iloc[0]) for sku in deltas if (df["SKU"] == sku).any()}

    _init_sqlite()
    result = {}
    with _connect() as conn:
        for sku, delta in deltas.items():
            conn.execute(
                "UPDATE inventory SET Fisico = MAX(0, Fisico + ?) WHERE SKU = ?",
                (delta, sku),
            )
        for sku in deltas:
            row = conn.execute("SELECT Fisico FROM inventory WHERE SKU = ?", (sku,)).fetchone()
            if row:
                result[sku] = int(row[0])
    return result


def set_fisico(sku, valor, csv_path="inventario_data.csv"):
    """Fija el Físico de un único SKU de forma puntual (conciliación/limpieza),
    sin reescribir el resto de la tabla."""
    sku = str(sku).upper().strip()
    valor = max(0, int(valor))
    if STORAGE_BACKEND == "csv":
        base = pd.read_csv(csv_path) if os.path.exists(csv_path) else _empty_inventory({})
        df = normalize_inventory(base, {})
        df.loc[df["SKU"] == sku, "Físico"] = valor
        df.to_csv(csv_path, index=False)
        return
    _init_sqlite()
    with _connect() as conn:
        conn.execute("UPDATE inventory SET Fisico = ? WHERE SKU = ?", (valor, sku))


def append_movement(sku, tipo, cantidad, nota="", csv_path="historial_movimientos.csv"):
    entry = {
        "Fecha": now_text(),
        "SKU": sku,
        "Tipo": tipo,
        "Cantidad": cantidad,
        "Nota": nota,
    }
    if STORAGE_BACKEND == "csv":
        pd.DataFrame([entry]).to_csv(csv_path, mode="a", header=not os.path.exists(csv_path), index=False)
        return

    _init_sqlite()
    with _connect() as conn:
        _seed_table_from_csv_if_empty(
            conn,
            "movement_history",
            csv_path,
            ["Fecha", "SKU", "Tipo", "Cantidad", "Nota"],
        )
        conn.execute(
            "INSERT INTO movement_history (Fecha, SKU, Tipo, Cantidad, Nota) VALUES (?, ?, ?, ?, ?)",
            (entry["Fecha"], entry["SKU"], entry["Tipo"], entry["Cantidad"], entry["Nota"]),
        )


def append_sale(sku, product, cantidad, referencia="", csv_path="historial_ventas.csv"):
    entry = {
        "Fecha": now_text(),
        "SKU": sku,
        "Producto": product,
        "Cantidad": cantidad,
        "Referencia": referencia,
    }
    if STORAGE_BACKEND == "csv":
        pd.DataFrame([entry]).to_csv(csv_path, mode="a", header=not os.path.exists(csv_path), index=False)
        return

    _init_sqlite()
    with _connect() as conn:
        _seed_table_from_csv_if_empty(
            conn,
            "sales_history",
            csv_path,
            ["Fecha", "SKU", "Producto", "Cantidad", "Referencia"],
        )
        conn.execute(
            "INSERT INTO sales_history (Fecha, SKU, Producto, Cantidad, Referencia) VALUES (?, ?, ?, ?, ?)",
            (entry["Fecha"], entry["SKU"], entry["Producto"], entry["Cantidad"], entry["Referencia"]),
        )


def append_invoice_lines(items, numero_factura, cliente="", oc="", usuario="", nota="", csv_path="historial_facturas.csv"):
    fecha = now_text()
    rows = [
        {
            "Fecha": fecha,
            "NumeroFactura": numero_factura,
            "Cliente": cliente,
            "OC": oc,
            "Usuario": usuario,
            "SKU": item["SKU"],
            "Producto": item["Producto"],
            "Cantidad": item["Cantidad"],
            "Estado": "Activa",
            "Nota": nota,
            "FechaAnulacion": "",
            "UsuarioAnulacion": "",
            "MotivoAnulacion": "",
        }
        for item in items
    ]
    if not rows:
        return

    invoice_df = pd.DataFrame(rows)
    if STORAGE_BACKEND == "csv":
        invoice_df.to_csv(csv_path, mode="a", header=not os.path.exists(csv_path), index=False)
        return

    _init_sqlite()
    with _connect() as conn:
        invoice_df.to_sql("invoice_lines", conn, if_exists="append", index=False)


def read_invoices(csv_path="historial_facturas.csv"):
    columns = [
        "Fecha",
        "NumeroFactura",
        "Cliente",
        "OC",
        "Usuario",
        "SKU",
        "Producto",
        "Cantidad",
        "Estado",
        "Nota",
        "FechaAnulacion",
        "UsuarioAnulacion",
        "MotivoAnulacion",
    ]
    if STORAGE_BACKEND == "csv":
        if not os.path.exists(csv_path):
            return pd.DataFrame(columns=columns)
        return pd.read_csv(csv_path)

    _init_sqlite()
    with _connect() as conn:
        return pd.read_sql_query("SELECT * FROM invoice_lines", conn)


def mark_invoice_cancelled(numero_factura, usuario="", motivo="", csv_path="historial_facturas.csv"):
    fecha = now_text()
    if STORAGE_BACKEND == "csv":
        invoices = read_invoices(csv_path)
        if invoices.empty:
            return 0
        mask = (invoices["NumeroFactura"].astype(str) == str(numero_factura)) & (invoices["Estado"] == "Activa")
        count = int(mask.sum())
        invoices.loc[mask, ["Estado", "FechaAnulacion", "UsuarioAnulacion", "MotivoAnulacion"]] = [
            "Anulada",
            fecha,
            usuario,
            motivo,
        ]
        invoices.to_csv(csv_path, index=False)
        return count

    _init_sqlite()
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE invoice_lines
            SET Estado = 'Anulada',
                FechaAnulacion = ?,
                UsuarioAnulacion = ?,
                MotivoAnulacion = ?
            WHERE NumeroFactura = ? AND Estado = 'Activa'
            """,
            (fecha, usuario, motivo, str(numero_factura)),
        )
        return cur.rowcount


def append_conciliation(df, csv_path="historial_conciliaciones.csv"):
    log_df = df.copy()
    log_df["Fecha_Conciliacion"] = now_text()
    columns = ["Fecha_Conciliacion", "SKU", "Producto", "Stock_Contifico", "Fisico_Real", "Diferencia"]
    log_df = log_df[columns]

    if STORAGE_BACKEND == "csv":
        log_df.to_csv(csv_path, mode="a", header=not os.path.exists(csv_path), index=False)
        return

    _init_sqlite()
    with _connect() as conn:
        _seed_table_from_csv_if_empty(conn, "conciliation_history", csv_path, columns)
        log_df.to_sql("conciliation_history", conn, if_exists="append", index=False)


def read_history(kind, csv_path):
    if STORAGE_BACKEND == "csv":
        if not os.path.exists(csv_path):
            return pd.DataFrame()
        return pd.read_csv(csv_path)

    _init_sqlite()
    table = {
        "movements": "movement_history",
        "sales": "sales_history",
        "conciliations": "conciliation_history",
    }[kind]
    columns = {
        "movements": ["Fecha", "SKU", "Tipo", "Cantidad", "Nota"],
        "sales": ["Fecha", "SKU", "Producto", "Cantidad", "Referencia"],
        "conciliations": ["Fecha_Conciliacion", "SKU", "Producto", "Stock_Contifico", "Fisico_Real", "Diferencia"],
    }[kind]
    with _connect() as conn:
        _seed_table_from_csv_if_empty(conn, table, csv_path, columns)
        return pd.read_sql_query(f"SELECT * FROM {table}", conn)


def storage_label():
    if STORAGE_BACKEND == "csv":
        return "CSV local"
    return f"SQLite local ({DB_PATH})"
