import streamlit as st
import pandas as pd
import re
import base64
import unicodedata
import order_parsers  # Nuevo módulo para procesar PDFs de cadenas
import storage

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Gestión de Operaciones | Inventario",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo visual sobrio para uso operativo diario.
st.markdown("""
    <style>
    :root {
        --surface: rgba(255, 255, 255, 0.76);
        --line: rgba(15, 23, 42, 0.12);
        --muted: rgba(71, 85, 105, 0.86);
        --accent: #0f766e;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    h1, h2, h3 {
        letter-spacing: 0;
    }
    .app-hero {
        border: 1px solid var(--line);
        border-left: 5px solid var(--accent);
        border-radius: 8px;
        padding: 16px 18px;
        margin-bottom: 14px;
        background: var(--surface);
    }
    .app-hero h1 {
        font-size: 1.65rem;
        line-height: 1.2;
        margin: 0 0 4px 0;
    }
    .app-hero p {
        color: var(--muted);
        margin: 0;
        font-size: 0.95rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 1px solid var(--line);
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 12px;
        border-radius: 6px 6px 0 0;
        font-size: 0.86rem;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(15, 118, 110, 0.10) !important;
        color: var(--accent) !important;
    }
    [data-testid="stMetric"] {
        padding: 14px 16px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--surface);
    }
    [data-testid="stMetricLabel"] {
        color: var(--muted);
    }
    section[data-testid="stSidebar"] {
        border-right: 1px solid var(--line);
    }
    div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
        border: 1px solid var(--line);
        border-radius: 8px;
        overflow: hidden;
    }
    .brand-line {
        display: flex;
        align-items: center;
        gap: 9px;
        margin: 0 0 12px 0;
    }
    .brand-badge {
        width: 30px;
        height: 30px;
        border-radius: 8px;
        background: var(--accent);
        color: #fff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1rem;
    }
    .brand-name {
        font-size: 1.02rem;
        font-weight: 600;
        line-height: 1.1;
    }
    .daycard {
        border: 1px solid var(--line);
        border-left: 4px solid var(--accent);
        border-radius: 8px;
        padding: 10px 14px;
        background: var(--surface);
        margin-bottom: 8px;
        font-size: 0.96rem;
    }
    .day-note {
        color: var(--accent);
        font-weight: 600;
    }
    .reminder {
        font-size: 0.85rem;
        color: var(--muted);
        margin-bottom: 14px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONSTANTES Y CARGA DE DATOS ---
DB_FILE = "inventario_data.csv"
HISTORY_FILE = "historial_movimientos.csv"
CONCILIATION_HISTORY = "historial_conciliaciones.csv"
SALES_HISTORY = "historial_ventas.csv"
INVOICE_HISTORY = "historial_facturas.csv"

CATALOGO = {
    "ACP001": "Toallitas húmedas x 100",
    "AE001": "Shampoo Ana Elixir Romero 370 ML.",
    "AE002": "Acondicionador Ana Elixir Romero 370 ML.",
    "AE003": "Pack SH + AC Ana Elixir Romero 370 ML.",
    "AR001": "Shampoo Ana Regenext 400 ML.",
    "AR002": "Acondicionador Ana Regenext 400 ML.",
    "AR003": "Tratamiento Capilar Ana Regenext 280 ML.",
    "AR004": "Crema de Peinar Ana Regenext 200 ML.",
    "AR005": "Shampoo Ana Regenext Sachet 18 ML.",
    "AR006": "Acondicionador Ana Regenext Sachet 18 ML.",
    "AR007": "Shampoo Ana Baby 400 ML."
}

# --- CONFIG EDITABLE DEL PANEL DE INICIO ---
# Nota que aparece según el día de la semana (lunes=0 ... domingo=6).
# Solo está puesto el ejemplo de martes; completa los demás cuando quieras.
NOTA_POR_DIA = {
    0: "",
    1: "Normalmente se factura Coral.",
    2: "",
    3: "",
    4: "",
    5: "",
    6: "",
}
# Recordatorios fijos que se muestran en Inicio (edítalos a tu gusto).
RECORDATORIOS = [
    "Revisa el turno de bodega antes de despachar.",
]
DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def saludo_fecha():
    dt = storage.now_dt()
    dia = DIAS_ES[dt.weekday()]
    fecha = f"{dt.day} de {MESES_ES[dt.month - 1]} de {dt.year}"
    return dia, fecha, NOTA_POR_DIA.get(dt.weekday(), "")


def load_data():
    return storage.load_inventory(CATALOGO, DB_FILE, uxc_map=order_parsers.UXC_MAP)

def save_data(df):
    storage.save_inventory(df, DB_FILE)

def log_movement(sku, tipo, cantidad, nota=""):
    storage.append_movement(sku, tipo, cantidad, nota, HISTORY_FILE)

def log_conciliation(conciliation_df):
    storage.append_conciliation(conciliation_df, CONCILIATION_HISTORY)

def log_sale(sku, cantidad, referencia=""):
    storage.append_sale(sku, CATALOGO.get(sku, "Desconocido"), cantidad, referencia, SALES_HISTORY)

def log_invoice(items, numero_factura, cliente="", oc="", usuario="", nota=""):
    storage.append_invoice_lines(items, numero_factura, cliente, oc, usuario, nota, INVOICE_HISTORY)

def _uxc_for_sku(sku):
    sku = str(sku).upper().strip()
    if "df" in globals() and sku in df["SKU"].values:
        return int(df.loc[df["SKU"] == sku, "UXC"].iloc[0])
    return int(order_parsers.UXC_MAP.get(sku, 12))

def _cantidad_total(modo, cajas, unidades, uxc):
    cajas = 0 if pd.isna(cajas) else int(cajas)
    unidades = 0 if pd.isna(unidades) else int(unidades)
    if modo == "Cajas":
        return max(0, cajas * int(uxc) + unidades)
    return max(0, unidades)

def _packaging_label(unidades, uxc):
    unidades = 0 if pd.isna(unidades) else int(unidades)
    if unidades < 0:
        return "-" + storage.format_cajas_sueltas(abs(unidades), uxc)
    return storage.format_cajas_sueltas(unidades, uxc)

def _norm_name(texto):
    """Normaliza un nombre de producto para comparar: mayúsculas, sin tildes,
    solo alfanumérico. Evita que 'ML.' vs 'ML' o una tilde rompan el match."""
    s = str(texto).upper()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Z0-9]", "", s)


def process_kardex(file):
    try:
        k_df = pd.read_excel(file, skiprows=4)
        k_df = k_df.dropna(subset=['Producto', 'Stock U'])
        if k_df.empty: return None
        k_df['Producto'] = k_df['Producto'].str.upper().str.strip()
        nombre_detectado = k_df['Producto'].iloc[0]
        stock_teorico = k_df['Stock U'].iloc[0]
        return {"producto": nombre_detectado, "stock_teorico": stock_teorico}
    except Exception as e:
        st.error(f"Error procesando Kardex: {e}")
        return None

# --- LÓGICA DE NEGOCIO ---
df = load_data()
df["Disponible"] = df["Físico"] - df["Reservado"]

def calculate_status(row):
    if row["Disponible"] <= 0: return "🔴 Agotado"
    if row["Disponible"] <= row["Min_Alert"]: return "🟡 Crítico"
    return "🟢 Disponible"

df["Estado"] = df.apply(calculate_status, axis=1)
df["Físico C/U"] = df.apply(lambda r: _packaging_label(r["Físico"], r["UXC"]), axis=1)
df["Disponible C/U"] = df.apply(lambda r: _packaging_label(r["Disponible"], r["UXC"]), axis=1)

# --- SIDEBAR: marca + navegación + carga rápida ---
with st.sidebar:
    st.markdown(
        """
        <div class="brand-line">
            <span class="brand-badge">📦</span>
            <span class="brand-name">Inventario HBECO</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    zona = st.radio(
        "Navegación",
        ["🏠 Inicio", "🛠️ Operar", "📊 Consultar", "🔍 Auditar", "⚙️ Configurar"],
        label_visibility="collapsed",
        key="zona_principal",
    )
    st.caption(f"{storage.storage_label()} · {storage.now_display()} ({storage.timezone_label()})")
    st.markdown("---")
    st.markdown("##### Carga rápida")
    metodo = st.radio("Método de Entrada", ["Individual", "Lote de Texto", "Importar Archivo", "Foto de Bodega"], label_visibility="collapsed")
    st.markdown("---")

    if metodo == "Individual":
        st.subheader("Registrar Movimiento")
        tipo = st.selectbox("Acción", ["Entrada de Fábrica", "Por Recibir", "Reservar", "Liberar Reserva", "Ajuste Directo"])
        prod_list = [f"{r['SKU']} | {r['Producto']}" for _, r in df.iterrows()]
        seleccion = st.selectbox("Producto", prod_list)
        sku = seleccion.split(" | ")[0]
        uxc = _uxc_for_sku(sku)
        modo_cantidad = st.radio("Ingresar como", ["Unidades", "Cajas"], horizontal=True, key="mov_modo")
        if modo_cantidad == "Cajas":
            cajas_mov = st.number_input("Cajas", step=1, value=0, min_value=0)
            unidades_mov = st.number_input("Unidades sueltas", step=1, value=0, min_value=0, max_value=max(uxc - 1, 0))
            cantidad = _cantidad_total("Cajas", cajas_mov, unidades_mov, uxc)
            st.caption(f"Total: {cantidad} unidades")
        else:
            cantidad = st.number_input("Unidades", step=1, value=0, min_value=0)
            st.caption(f"Equivale a {_packaging_label(cantidad, uxc)}")
        nota = st.text_input("Nota / Referencia")

        if st.button("Ejecutar Registro", width="stretch"):
            col = {"Entrada de Fábrica": "Físico", "Por Recibir": "Por Recibir", "Reservar": "Reservado", "Liberar Reserva": "Reservado", "Ajuste Directo": "Físico"}[tipo]
            if tipo == "Ajuste Directo":
                df.loc[df["SKU"] == sku, col] = cantidad
            elif tipo == "Liberar Reserva":
                actual = int(df.loc[df["SKU"] == sku, col].iloc[0])
                df.loc[df["SKU"] == sku, col] = max(0, actual - cantidad)
            else:
                df.loc[df["SKU"] == sku, col] += cantidad
            save_data(df)
            log_movement(sku, tipo, cantidad, nota)
            st.rerun()

    elif metodo == "Lote de Texto":
        st.subheader("Carga por Lote")
        st.caption("Formato: SKU, Cantidad")
        batch_input = st.text_area("Lista", height=150)
        tipo_batch = st.selectbox("Acción para el lote", ["Entrada de Fábrica", "Por Recibir", "Reservar"])
        if st.button("Procesar Lista", width="stretch"):
            for line in batch_input.strip().split("\n"):
                try:
                    parts = line.replace(" ", "").split(",")
                    if len(parts) == 2:
                        s, c = parts
                        if s.upper() in df["SKU"].values:
                            col = {"Entrada de Fábrica": "Físico", "Por Recibir": "Por Recibir", "Reservar": "Reservado"}[tipo_batch]
                            df.loc[df["SKU"] == s.upper(), col] += int(c)
                            log_movement(s.upper(), f"Lote: {tipo_batch}", int(c), "Carga manual")
                except: continue
            save_data(df)
            st.rerun()

    elif metodo == "Importar Archivo":
        st.subheader("Carga Masiva")
        file = st.file_uploader("Subir Excel o CSV", type=["xlsx", "csv"])
        if file:
            try:
                idf = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
                idf.columns = [c.upper().strip() for c in idf.columns]
                c_sku = next((c for c in ["SKU", "CODIGO", "REFERENCIA"] if c in idf.columns), None)
                c_qty = next((c for c in ["FISICO", "STOCK", "CANTIDAD"] if c in idf.columns), None)
                if c_sku and c_qty and st.button("Confirmar Importación"):
                    for _, r in idf.iterrows():
                        sku_val = str(r[c_sku]).upper()
                        if sku_val in df["SKU"].values:
                            df.loc[df["SKU"] == sku_val, "Físico"] = r[c_qty]
                    save_data(df)
                    log_movement("SISTEMA", "Importación Archivo", 0, file.name)
                    st.rerun()
            except Exception as e: st.error(f"Error: {e}")

    elif metodo == "Foto de Bodega":
        st.subheader("Cargar Reporte de Bodega (Imagen)")
        st.caption(
            "Sube la captura del Excel de bodega (columnas SKU | Descripción | UM | Saldo). "
            "El OCR es un punto de partida, no un dato confiable por sí solo: "
            "siempre revisa y corrige la tabla antes de confirmar."
        )
        bodega_img = st.file_uploader("Imagen del reporte (PNG/JPG)", type=["png", "jpg", "jpeg"], key="bodega_img")

        if bodega_img is not None and st.button("🔍 Leer imagen", width="stretch"):
            items, no_reconocidos, texto_ocr = order_parsers.parse_bodega_stock_image(bodega_img)
            st.session_state["bodega_ocr_texto"] = texto_ocr
            if items is None:
                st.error(no_reconocidos)
                st.session_state.pop("bodega_items", None)
                st.session_state.pop("bodega_no_reconocidos", None)
            elif not items and not no_reconocidos:
                st.warning(
                    "No se detectó ningún código de SKU. Revisa el texto OCR abajo, o usa una imagen "
                    "más nítida — evita reenviar por WhatsApp, comprime mucho la foto y empeora el OCR."
                )
                st.session_state.pop("bodega_items", None)
                st.session_state.pop("bodega_no_reconocidos", None)
            else:
                st.session_state["bodega_items"] = items
                st.session_state["bodega_no_reconocidos"] = no_reconocidos

        if st.session_state.get("bodega_ocr_texto"):
            with st.expander("🔧 Texto crudo detectado por el OCR (depuración)"):
                st.text(st.session_state["bodega_ocr_texto"])

        if st.session_state.get("bodega_items"):
            items = st.session_state["bodega_items"]
            preview_rows = []
            for it in items:
                actual = int(df.loc[df["SKU"] == it["SKU"], "Físico"].iloc[0]) if it["SKU"] in df["SKU"].values else 0
                # Si el OCR no logró leer el Saldo de esta fila, se deja el
                # Físico actual como valor por defecto: si el usuario no la
                # corrige, confirmar no cambia nada (nunca se pone en 0 solo).
                saldo_default = it["Saldo"] if it["Saldo"] is not None else actual
                preview_rows.append({
                    "SKU Bodega": it["SKU_Bodega"],
                    "SKU App": it["SKU"],
                    "Producto (detectado)": CATALOGO.get(it["SKU"], "Desconocido"),
                    "UM (uds/caja)": it["UM"] if it["UM"] is not None else 0,
                    "Saldo Bodega (uds)": saldo_default,
                    "Físico Actual App": actual,
                })

            st.markdown("### Revisa y corrige antes de aplicar")
            st.caption("Edita cualquier celda si el OCR se equivocó. Puedes agregar o borrar filas con el botón ➕/🗑️ de la tabla.")
            edited_bodega = st.data_editor(
                pd.DataFrame(preview_rows),
                column_config={
                    "SKU Bodega": st.column_config.TextColumn("SKU Bodega", disabled=True),
                    "SKU App": st.column_config.SelectboxColumn("SKU App", options=list(CATALOGO.keys()), required=True),
                    "Producto (detectado)": st.column_config.TextColumn("Producto (detectado)", disabled=True),
                    "UM (uds/caja)": st.column_config.NumberColumn("UM (uds/caja)", format="%d"),
                    "Saldo Bodega (uds)": st.column_config.NumberColumn("Saldo Bodega (uds)", format="%d"),
                    "Físico Actual App": st.column_config.NumberColumn("Físico Actual App", disabled=True, format="%d"),
                },
                width="stretch",
                hide_index=True,
                num_rows="dynamic",
                key="editor_bodega",
            )

            no_reconocidos = st.session_state.get("bodega_no_reconocidos") or []
            if no_reconocidos:
                st.warning(f"{len(no_reconocidos)} código(s) detectado(s) que no se pudieron asociar a ningún SKU del catálogo (no aparecen en la tabla de arriba). Cárgalos manualmente con 'Individual':")
                st.dataframe(pd.DataFrame(no_reconocidos), width="stretch", hide_index=True)

            if st.button("✅ Confirmar y actualizar Físico desde Bodega", type="primary", width="stretch"):
                aplicados = 0
                for _, row in edited_bodega.iterrows():
                    sku = row["SKU App"]
                    saldo = row["Saldo Bodega (uds)"]
                    if not sku or pd.isna(saldo):
                        continue
                    storage.set_fisico(sku, int(saldo), DB_FILE)
                    log_movement(sku, "Carga Bodega (Imagen)", int(saldo), f"SKU bodega {row['SKU Bodega']}")
                    aplicados += 1
                del st.session_state["bodega_items"]
                st.session_state.pop("bodega_no_reconocidos", None)
                st.success(f"✅ Físico actualizado para {aplicados} producto(s) desde el reporte de bodega.")
                st.rerun()

# --- CUERPO PRINCIPAL ---
st.markdown(
    f"""
    <div class="app-hero">
        <h1>Inventario Disponible</h1>
        <p>Control operativo de stock físico, reservas, producto por recibir y facturación trazable. Actualizado: {storage.now_display()}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Stock Físico", int(df["Físico"].sum()))
m2.metric("Disponible", int(df["Disponible"].sum()))
m3.metric("Reservado", int(df["Reservado"].sum()))
m4.metric("Alertas", len(df[df["Estado"] != "🟢 Disponible"]))

# --- ZONAS DE TRABAJO ---
# La navegación entre zonas vive en el menú lateral (st.radio "zona").
# En celular, Streamlit colapsa ese menú en el botón ☰.

if zona == "🏠 Inicio":
    dia, fecha, nota = saludo_fecha()
    nota_html = f' · <span class="day-note">{nota}</span>' if nota else ""
    st.markdown(
        f'<div class="daycard"><b>Hoy es {dia}</b>, {fecha}{nota_html}</div>',
        unsafe_allow_html=True,
    )
    if RECORDATORIOS:
        st.markdown(
            '<div class="reminder">🔔 ' + " · ".join(RECORDATORIOS) + "</div>",
            unsafe_allow_html=True,
        )

    # Estado del día (discreto): lo que necesita atención hoy.
    bajo_minimo = df[df["Estado"] != "🟢 Disponible"]

    hoy = storage.now_dt().strftime("%Y-%m-%d")
    inv_df = storage.read_invoices(INVOICE_HISTORY)
    fact_hoy = 0
    if not inv_df.empty and "Cantidad" in inv_df.columns:
        mask_hoy = (inv_df["Estado"] == "Activa") & (inv_df["Fecha"].astype(str).str.startswith(hoy))
        fact_hoy = int(pd.to_numeric(inv_df.loc[mask_hoy, "Cantidad"], errors="coerce").fillna(0).sum())

    conc_df = storage.read_history("conciliations", CONCILIATION_HISTORY)
    ultima_conc = "—"
    if not conc_df.empty:
        fechas_conc = pd.to_datetime(conc_df["Fecha_Conciliacion"], errors="coerce").dropna()
        if not fechas_conc.empty:
            ultima_conc = fechas_conc.max().strftime("%d/%m/%Y")

    d1, d2, d3 = st.columns(3)
    d1.metric("Productos bajo mínimo", len(bajo_minimo))
    d2.metric("Facturado hoy (uds)", fact_hoy)
    d3.metric("Última conciliación", ultima_conc)

    if not bajo_minimo.empty:
        st.markdown("##### Requieren atención")
        st.dataframe(
            bajo_minimo[["SKU", "Producto", "Disponible", "Disponible C/U", "Estado"]],
            width="stretch",
            hide_index=True,
        )
    else:
        st.success("Todo el inventario está sobre el mínimo. 👍")

elif zona == "🛠️ Operar":
    tab_fact, tab_oc, tab_pre = st.tabs(["📄 Facturación", "📦 Órdenes (OC)", "✅ Pre-validación"])

    with tab_fact:
        st.subheader("Registro de Facturación")
        st.info("La factura descuenta stock físico y queda registrada por número para trazabilidad y anulación.")
        meta1, meta2, meta3, meta4 = st.columns(4)
        numero_factura = meta1.text_input("Número de factura")
        cliente_factura = meta2.text_input("Cliente / Cadena")
        oc_factura = meta3.text_input("OC relacionada")
        usuario_factura = meta4.text_input("Usuario")

        st.markdown("### Entrada Manual")
        manual_base = pd.DataFrame([
            {"SKU": "", "Modo": "Unidades", "Cajas": 0, "Unidades": 0}
        ])
        manual_fact = st.data_editor(
            manual_base,
            column_config={
                "SKU": st.column_config.SelectboxColumn("SKU", options=[""] + list(CATALOGO.keys()), required=False),
                "Modo": st.column_config.SelectboxColumn("Modo", options=["Unidades", "Cajas"], required=True),
                "Cajas": st.column_config.NumberColumn("Cajas", min_value=0, step=1, format="%d"),
                "Unidades": st.column_config.NumberColumn("Unidades", min_value=0, step=1, format="%d"),
            },
            width="stretch",
            hide_index=True,
            num_rows="dynamic",
            key="manual_fact_editor",
        )
        manual_preview_rows = []
        for _, row in manual_fact.iterrows():
            sku_manual = str(row.get("SKU", "")).upper().strip()
            if not sku_manual:
                continue
            uxc_manual = _uxc_for_sku(sku_manual)
            total_manual = _cantidad_total(row.get("Modo", "Unidades"), row.get("Cajas", 0), row.get("Unidades", 0), uxc_manual)
            if total_manual <= 0:
                continue
            manual_preview_rows.append({
                "SKU": sku_manual,
                "Producto": CATALOGO.get(sku_manual, "Desconocido"),
                "UXC": uxc_manual,
                "Total unidades": total_manual,
                "Equivalencia": _packaging_label(total_manual, uxc_manual),
            })
        if manual_preview_rows:
            st.dataframe(pd.DataFrame(manual_preview_rows), width="stretch", hide_index=True)

        col_text, col_pdf = st.columns(2)

        with col_text:
            st.markdown("### ⌨️ Por Texto")
            fact_text = st.text_area("Pega aquí el detalle", height=150, placeholder="12.00 SHAMPOO ANA REGENEXT 400 ML. -", key="fact_area")

        with col_pdf:
            st.markdown("### 📄 Por PDF")
            fact_files = st.file_uploader("Subir Facturas (PDF)", type=["pdf"], accept_multiple_files=True)

        if st.button("🔍 Analizar y Consolidar Movimiento", width="stretch"):
            consolidado = {}
            processed_logs = []
            errors = []

            for item in manual_preview_rows:
                sku = item["SKU"]
                qty = int(item["Total unidades"])
                consolidado[sku] = consolidado.get(sku, 0) + qty
                processed_logs.append((sku, qty, "Manual cajas/unidades"))

            # Procesar Texto
            if fact_text:
                lines = fact_text.strip().split("\n")
                for line in lines:
                    if not line.strip(): continue
                    qty_match = re.search(r'(\d+[\.,]\d+|\d+)', line)
                    if qty_match:
                        qty = int(float(qty_match.group(1).replace(",", ".")))
                        product_text = line.replace(qty_match.group(0), "", 1).strip()
                        sku = order_parsers.get_sku_from_text(product_text)
                        if sku:
                            consolidado[sku] = consolidado.get(sku, 0) + qty
                            processed_logs.append((sku, qty, "Manual / Texto"))
                        else: errors.append(f"No reconocido (Texto): {line[:30]}")

            # Procesar PDFs
            if fact_files:
                for f in fact_files:
                    # Usamos el detector de cadenas pero para facturas genéricas
                    _, items = order_parsers.detect_chain_and_parse(f)
                    if items:
                        for item in items:
                            sku = item["SKU"]
                            qty = item["Cantidad"]
                            consolidado[sku] = consolidado.get(sku, 0) + qty
                            processed_logs.append((sku, qty, f"PDF: {f.name}"))
                    else: errors.append(f"No se pudo leer: {f.name}")

            if consolidado:
                st.session_state["consolidado_fact"] = consolidado
                st.session_state["logs_fact"] = processed_logs
                st.session_state["errors_fact"] = errors
            else:
                st.error("No se detectó ningún dato válido.")

        if "consolidado_fact" in st.session_state:
            st.markdown("---")
            st.markdown("### 📋 Resumen a Descontar")
            res_data = []
            for k, v in st.session_state["consolidado_fact"].items():
                disponible = int(df.loc[df["SKU"] == k, "Disponible"].iloc[0]) if k in df["SKU"].values else 0
                uxc = _uxc_for_sku(k)
                res_data.append({
                    "SKU": k,
                    "Producto": CATALOGO.get(k, "Desconocido"),
                    "Total unidades": v,
                    "Total cajas/u.": _packaging_label(v, uxc),
                    "Disponible": disponible,
                    "Disponible cajas/u.": _packaging_label(disponible, uxc),
                    "Alcanza": "SÍ" if disponible >= v else "NO",
                })
            resumen_df = pd.DataFrame(res_data)
            st.dataframe(resumen_df, width="stretch", hide_index=True)

            if st.button("✅ CONFIRMAR FACTURA Y RESTAR STOCK", type="primary", width="stretch"):
                if not numero_factura.strip():
                    st.error("El número de factura es obligatorio.")
                    st.stop()
                if not usuario_factura.strip():
                    st.error("El usuario es obligatorio para trazabilidad.")
                    st.stop()
                if (resumen_df["Alcanza"] == "NO").any():
                    st.error("No se puede facturar: hay productos sin stock disponible suficiente.")
                    st.stop()

                invoice_items = []
                deltas = {}
                for sku, qty in st.session_state["consolidado_fact"].items():
                    deltas[sku] = deltas.get(sku, 0) - qty
                    referencia = f"Factura {numero_factura} | Cliente: {cliente_factura or 'S/N'} | OC: {oc_factura or 'S/N'}"
                    log_movement(sku, "FACTURA", -qty, referencia)
                    log_sale(sku, qty, referencia)
                    invoice_items.append({"SKU": sku, "Producto": CATALOGO.get(sku, "Desconocido"), "Cantidad": qty})

                storage.adjust_stock(deltas, DB_FILE)
                log_invoice(invoice_items, numero_factura.strip(), cliente_factura.strip(), oc_factura.strip(), usuario_factura.strip(), "Factura registrada desde pestaña Facturación")
                st.success("🎉 Factura registrada, stock actualizado y ventas guardadas.")
                del st.session_state["consolidado_fact"]
                st.rerun()

    with tab_oc:
        st.subheader("Analizador de Órdenes de Compra (PDF)")

        oc_file = st.file_uploader("Subir PDF de Orden de Compra", type=["pdf"], key="oc_uploader")

        if oc_file:
            col_pdf, col_data = st.columns([1, 1])

            with col_pdf:
                st.markdown("### 📄 Vista Previa OC")
                base64_pdf = base64.b64encode(oc_file.read()).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
                # Reset file pointer for parsing
                oc_file.seek(0)

            with col_data:
                st.markdown("### 🔍 Validación y Despacho")
                cadena, items_oc = order_parsers.detect_chain_and_parse(oc_file)

                if items_oc:
                    st.success(f"✅ Detectado: **{cadena}**")
                    oc_meta1, oc_meta2, oc_meta3 = st.columns(3)
                    numero_factura_oc = oc_meta1.text_input("Número de factura", key="oc_factura_numero")
                    usuario_oc = oc_meta2.text_input("Usuario", key="oc_usuario")
                    oc_referencia = oc_meta3.text_input("OC / Referencia", key="oc_referencia")

                    oc_df = pd.DataFrame(items_oc)
                    oc_df['SKU'] = oc_df['SKU'].str.upper().str.strip()

                    # Unir con el inventario
                    validation_df = oc_df.merge(df[["SKU", "Producto", "UXC", "Disponible", "Físico"]], on="SKU", how="left")

                    # Calcular sugerencia de despacho
                    def suggest_qty(row):
                        if pd.isna(row["Disponible"]) or row["Disponible"] <= 0: return 0
                        return min(int(row["Cantidad"]), int(row["Disponible"]))

                    validation_df["Sugerencia"] = validation_df.apply(suggest_qty, axis=1)
                    validation_df["Pedido cajas/u."] = validation_df.apply(
                        lambda r: _packaging_label(r["Cantidad"], r["UXC"]) if not pd.isna(r["UXC"]) else "",
                        axis=1,
                    )
                    validation_df["Disponible cajas/u."] = validation_df.apply(
                        lambda r: _packaging_label(r["Disponible"], r["UXC"]) if not pd.isna(r["UXC"]) else "",
                        axis=1,
                    )
                    validation_df["Sugerencia cajas/u."] = validation_df.apply(
                        lambda r: _packaging_label(r["Sugerencia"], r["UXC"]) if not pd.isna(r["UXC"]) else "",
                        axis=1,
                    )
                    validation_df["Estado_V"] = validation_df.apply(
                        lambda r: "🟢" if r["Sugerencia"] == r["Cantidad"] else ("🟡" if r["Sugerencia"] > 0 else "🔴"),
                        axis=1
                    )

                    # Editor de despacho
                    st.write("Ajusta las cantidades si es necesario antes de confirmar:")
                    edited_oc = st.data_editor(
                        validation_df[["Estado_V", "Desc_Original", "Producto", "Cantidad", "Pedido cajas/u.", "Disponible", "Disponible cajas/u.", "Sugerencia", "Sugerencia cajas/u.", "SKU"]],
                        column_config={
                            "Estado_V": st.column_config.TextColumn(" ", width="small"),
                            "Desc_Original": st.column_config.TextColumn("OC Original (Izquierda)", disabled=True),
                            "Producto": st.column_config.TextColumn("Sistema (Derecha)", disabled=True),
                            "Cantidad": st.column_config.NumberColumn("Pedido OC", disabled=True),
                            "Pedido cajas/u.": st.column_config.TextColumn("Pedido cajas/u.", disabled=True),
                            "Disponible": st.column_config.NumberColumn("Disponible", disabled=True),
                            "Disponible cajas/u.": st.column_config.TextColumn("Disponible cajas/u.", disabled=True),
                            "Sugerencia": st.column_config.NumberColumn("A Despachar", format="%d"),
                            "Sugerencia cajas/u.": st.column_config.TextColumn("A despachar cajas/u.", disabled=True),
                            "SKU": st.column_config.TextColumn("SKU", disabled=True)
                        },
                        width="stretch",
                        hide_index=True,
                        key="editor_oc"
                    )

                    if st.button("🚀 Confirmar Facturación y Restar de Físico", width="stretch", type="primary"):
                        if not numero_factura_oc.strip():
                            st.error("El número de factura es obligatorio.")
                            st.stop()
                        if not usuario_oc.strip():
                            st.error("El usuario es obligatorio para trazabilidad.")
                            st.stop()

                        items_processed = 0
                        invoice_items = []
                        deltas = {}
                        for _, row in edited_oc.iterrows():
                            if row["Sugerencia"] > 0:
                                qty = int(row["Sugerencia"])
                                sku = row["SKU"]
                                deltas[sku] = deltas.get(sku, 0) - qty
                                referencia = f"Factura {numero_factura_oc} | Cliente: {cadena} | OC: {oc_referencia or 'S/N'}"
                                log_movement(sku, f"VENTA OC: {cadena}", -qty, referencia)
                                log_sale(sku, qty, referencia)
                                invoice_items.append({"SKU": sku, "Producto": row["Producto"], "Cantidad": qty})
                                items_processed += 1

                        if items_processed > 0:
                            storage.adjust_stock(deltas, DB_FILE)
                            log_invoice(invoice_items, numero_factura_oc.strip(), cadena, oc_referencia.strip(), usuario_oc.strip(), "Factura registrada desde OC")
                            st.success(f"✅ Se han facturado {items_processed} productos. El stock físico ha sido actualizado.")
                            st.rerun()
                else:
                    st.error("No se pudieron extraer datos del PDF.")

    with tab_pre:
        st.subheader("Pre-validación de Facturas")
        pre_df = df[["SKU", "Producto", "UXC", "Disponible", "Disponible C/U"]].copy()
        pre_df["Modo"] = "Unidades"
        pre_df["Cajas"] = 0
        pre_df["Unidades"] = 0
        edited_pre = st.data_editor(
            pre_df,
            column_config={
                "SKU": st.column_config.TextColumn("SKU", disabled=True),
                "Producto": st.column_config.TextColumn("Producto", disabled=True),
                "UXC": st.column_config.NumberColumn("UXC", disabled=True, format="%d"),
                "Disponible": st.column_config.NumberColumn("Disponible", disabled=True),
                "Disponible C/U": st.column_config.TextColumn("Disponible cajas/u.", disabled=True),
                "Modo": st.column_config.SelectboxColumn("Modo", options=["Unidades", "Cajas"], required=True),
                "Cajas": st.column_config.NumberColumn("Cajas", min_value=0, step=1, format="%d"),
                "Unidades": st.column_config.NumberColumn("Unidades", min_value=0, step=1, format="%d"),
            },
            hide_index=True,
            width="stretch",
        )
        edited_pre["Cantidad a Facturar"] = edited_pre.apply(
            lambda r: _cantidad_total(r["Modo"], r["Cajas"], r["Unidades"], r["UXC"]),
            axis=1,
        )
        edited_pre["Pedido cajas/u."] = edited_pre.apply(
            lambda r: _packaging_label(r["Cantidad a Facturar"], r["UXC"]),
            axis=1,
        )
        items_pedido = edited_pre[edited_pre["Cantidad a Facturar"] > 0].copy()
        if not items_pedido.empty:
            items_pedido["Alcanza"] = items_pedido.apply(lambda r: "🟢 SÍ" if r["Disponible"] >= r["Cantidad a Facturar"] else "🔴 NO", axis=1)
            if all(items_pedido["Alcanza"] == "🟢 SÍ"): st.success("### ✅ PUEDES FACTURAR")
            else: st.error("### ❌ NO FACTURAR")
            st.dataframe(items_pedido[["SKU", "Producto", "Disponible", "Disponible C/U", "Cantidad a Facturar", "Pedido cajas/u.", "Alcanza"]], width="stretch", hide_index=True)

elif zona == "📊 Consultar":
    tab_inv, tab_ventas, tab_his, tab_rep, tab_est = st.tabs(["📋 Inventario", "💰 Ventas", "🕓 Historial", "🔁 Reabastecimiento", "📈 Estrategia"])

    with tab_inv:
        st.subheader("Control de Inventario")
        # Tabla editable para cambios rápidos
        df_editable = st.data_editor(
            df[["SKU", "Producto", "UXC", "Físico", "Físico C/U", "Reservado", "Disponible", "Disponible C/U", "Por Recibir", "Estado", "Nota_Alerta"]],
            column_config={
                "SKU": st.column_config.TextColumn("SKU", disabled=True),
                "Producto": st.column_config.TextColumn("Producto", disabled=True),
                "UXC": st.column_config.NumberColumn("UXC", disabled=True, format="%d"),
                "Disponible": st.column_config.NumberColumn("Disponible", disabled=True, format="%d"),
                "Disponible C/U": st.column_config.TextColumn("Disponible cajas/u.", disabled=True),
                "Estado": st.column_config.TextColumn("Estado", disabled=True),
                "Físico": st.column_config.NumberColumn("Físico", format="%d"),
                "Físico C/U": st.column_config.TextColumn("Físico cajas/u.", disabled=True),
                "Reservado": st.column_config.NumberColumn("Reservado", format="%d"),
                "Por Recibir": st.column_config.NumberColumn("Por Recibir", format="%d"),
                "Nota_Alerta": st.column_config.TextColumn("Observaciones")
            },
            width="stretch",
            hide_index=True,
            key="editor_inventario"
        )

        if st.button("💾 Guardar Cambios en Inventario", width="stretch"):
            # Actualizar el dataframe original con los cambios del editor
            for index, row in df_editable.iterrows():
                sku = row["SKU"]
                df.loc[df["SKU"] == sku, ["Físico", "Reservado", "Por Recibir", "Nota_Alerta"]] = [row["Físico"], row["Reservado"], row["Por Recibir"], row["Nota_Alerta"]]
            save_data(df)
            st.success("✅ Inventario actualizado correctamente.")
            st.rerun()

    with tab_ventas:
        st.subheader("Análisis de Ventas (Facturado)")
        invoices_df = storage.read_invoices(INVOICE_HISTORY)
        if not invoices_df.empty:
            st.markdown("### Facturas")
            invoices_display = invoices_df.copy()
            invoices_display["Fecha_Orden"] = pd.to_datetime(invoices_display["Fecha"], errors="coerce")
            invoices_display = invoices_display.sort_values(by="Fecha_Orden", ascending=False).drop(columns=["Fecha_Orden"])
            invoices_display["Fecha"] = storage.format_datetime_series(invoices_display["Fecha"])
            st.dataframe(invoices_display, width="stretch", hide_index=True)

            active_invoices = invoices_df[invoices_df["Estado"] == "Activa"].copy()
            if not active_invoices.empty:
                st.markdown("### Anular Factura")
                invoice_options = (
                    active_invoices[["NumeroFactura", "Cliente", "OC"]]
                    .drop_duplicates()
                    .assign(
                        label=lambda x: x["NumeroFactura"].astype(str)
                        + " | "
                        + x["Cliente"].fillna("").astype(str)
                        + " | OC: "
                        + x["OC"].fillna("").astype(str)
                    )
                )
                factura_anular = st.selectbox("Factura activa", invoice_options["label"].tolist())
                numero_anular = factura_anular.split(" | ")[0]
                lineas_anular = active_invoices[active_invoices["NumeroFactura"].astype(str) == numero_anular]
                st.dataframe(lineas_anular[["SKU", "Producto", "Cantidad", "Cliente", "OC", "Usuario"]], width="stretch", hide_index=True)

                anul_col1, anul_col2, anul_col3 = st.columns(3)
                usuario_anula = anul_col1.text_input("Usuario que anula")
                motivo_anula = anul_col2.text_input("Motivo")
                confirma_anula = anul_col3.text_input("Escribe ANULAR")

                if st.button("Anular factura y devolver stock", type="primary", width="stretch"):
                    if confirma_anula != "ANULAR":
                        st.error("Para anular debes escribir ANULAR.")
                        st.stop()
                    if not usuario_anula.strip() or not motivo_anula.strip():
                        st.error("Usuario y motivo son obligatorios.")
                        st.stop()

                    deltas = {}
                    for _, row in lineas_anular.iterrows():
                        qty = int(row["Cantidad"])
                        sku = row["SKU"]
                        deltas[sku] = deltas.get(sku, 0) + qty
                        log_movement(sku, "ANULACIÓN FACTURA", qty, f"Factura {numero_anular}: {motivo_anula}")
                        log_sale(sku, -qty, f"Anulación factura {numero_anular}: {motivo_anula}")

                    storage.adjust_stock(deltas, DB_FILE)
                    updated = storage.mark_invoice_cancelled(numero_anular, usuario_anula.strip(), motivo_anula.strip(), INVOICE_HISTORY)
                    st.success(f"Factura {numero_anular} anulada. Líneas actualizadas: {updated}.")
                    st.rerun()

        s_df = storage.read_history("sales", SALES_HISTORY)
        if not s_df.empty:
            s_df["Fecha_Orden"] = pd.to_datetime(s_df["Fecha"], errors="coerce")

            col_v1, col_v2 = st.columns([1, 2])

            with col_v1:
                st.markdown("### Top Productos")
                top_v = s_df.groupby("Producto")["Cantidad"].sum().sort_values(ascending=False)
                st.dataframe(top_v)

            with col_v2:
                st.markdown("### Ventas por Producto")
                st.bar_chart(top_v)

            st.markdown("### Historial Detallado")
            s_display = s_df.sort_values(by="Fecha_Orden", ascending=False).drop(columns=["Fecha_Orden"])
            s_display["Fecha"] = storage.format_datetime_series(s_display["Fecha"])
            st.dataframe(s_display, width="stretch", hide_index=True)
        else:
            st.info("Aún no hay ventas registradas.")

    with tab_his:
        st.subheader("Análisis de Stock")
        st.bar_chart(df.set_index("Producto")["Físico"])
        st.markdown("---")
        h_df = storage.read_history("movements", HISTORY_FILE)
        if not h_df.empty:
            h_df["Fecha_Orden"] = pd.to_datetime(h_df["Fecha"], errors="coerce")
            h_display = h_df.sort_values(by="Fecha_Orden", ascending=False).drop(columns=["Fecha_Orden"])
            h_display["Fecha"] = storage.format_datetime_series(h_display["Fecha"])
            st.dataframe(h_display, width="stretch", hide_index=True)

    with tab_rep:
        st.subheader("Necesidades de Reabastecimiento")
        rep_df = df[df["Estado"] != "🟢 Disponible"].copy()
        if not rep_df.empty:
            rep_df["Sugerencia"] = (rep_df["Min_Alert"] * 2) - rep_df["Disponible"]
            st.table(rep_df[["SKU", "Producto", "Disponible", "Estado", "Sugerencia"]])
        else: st.info("Todo optimizado.")

    with tab_est:
        st.subheader("Reporte Ejecutivo y Estrategia")
        c_df = storage.read_history("conciliations", CONCILIATION_HISTORY)
        if not c_df.empty:
            c_df = c_df.merge(df[["SKU", "Costo"]], on="SKU", how="left")
            c_df["Valor_Diferencia"] = c_df["Diferencia"] * c_df["Costo"]
            total_perdida = c_df[c_df["Diferencia"] < 0]["Valor_Diferencia"].sum()
            precision = (1 - (abs(c_df["Diferencia"]).sum() / df["Físico"].sum())) * 100 if df["Físico"].sum() > 0 else 100
            e1, e2 = st.columns(2)
            e1.metric("Pérdida Acumulada", f"${abs(total_perdida):,.2f}")
            e2.metric("Precisión Bodega", f"{precision:.1f}%")
            st.markdown("### SKUs con más descuadres")
            if not c_df[c_df["Diferencia"] != 0].empty:
                st.bar_chart(c_df[c_df["Diferencia"] != 0]["Producto"].value_counts().head(5))
            c_df["Fecha_Orden"] = pd.to_datetime(c_df["Fecha_Conciliacion"], errors="coerce")
            c_display = c_df.sort_values(by="Fecha_Orden", ascending=False).drop(columns=["Fecha_Orden"])
            c_display["Fecha_Conciliacion"] = storage.format_datetime_series(c_display["Fecha_Conciliacion"])
            st.dataframe(c_display, width="stretch", hide_index=True)
        else: st.info("Sin datos estratégicos aún.")

elif zona == "🔍 Auditar":
    st.subheader("Conciliación Individual por Producto")
    kardex_file = st.file_uploader("Subir Kardex del Producto (Excel)", type=["xlsx"])
    if kardex_file:
        resumen_k = process_kardex(kardex_file)
        if resumen_k:
            prod_nom = resumen_k["producto"]
            stock_contifico = resumen_k["stock_teorico"]
            objetivo = _norm_name(prod_nom)
            df['Producto_Norm'] = df['Producto'].apply(_norm_name)
            match = df[df['Producto_Norm'] == objetivo]
            if match.empty and objetivo:
                # Respaldo: coincidencia parcial en cualquier sentido
                match = df[df['Producto_Norm'].apply(lambda n: bool(n) and (n in objetivo or objetivo in n))]
            if not match.empty:
                sku_detectado = match.iloc[0]['SKU']
                nombre_app = match.iloc[0]['Producto']
                fisico_actual = match.iloc[0]['Físico']
                st.success(f"✅ Producto Detectado: **{nombre_app}**")
                col1, col2, col3 = st.columns(3)
                col1.metric("Contífico", f"{stock_contifico:,.0f}")
                col2.metric("App Actual", f"{fisico_actual:,.0f}")
                nuevo_fisico = col3.number_input("Físico Real", value=float(fisico_actual), step=1.0)
                diferencia = nuevo_fisico - stock_contifico
                if diferencia == 0: st.success("🟢 Cuadrado")
                elif abs(diferencia) <= 5: st.warning(f"🟡 Desfase: {diferencia}")
                else: st.error(f"🔴 Descuadrado: {diferencia}")
                if st.button("Confirmar y Actualizar"):
                    storage.set_fisico(sku_detectado, nuevo_fisico, DB_FILE)
                    log_df = pd.DataFrame([{"SKU": sku_detectado, "Producto": nombre_app, "Stock_Contifico": stock_contifico, "Fisico_Real": nuevo_fisico, "Diferencia": diferencia}])
                    log_conciliation(log_df)
                    log_movement(sku_detectado, "Conciliación", nuevo_fisico, f"Kardex: {kardex_file.name}")
                    st.rerun()
            else: st.error("Producto no encontrado.")

elif zona == "⚙️ Configurar":
    st.subheader("Configuración de Sistema")

    # 1. Edición de Parámetros
    st.markdown("### 🛠️ Parámetros de Productos")
    cfg_edit = st.data_editor(
        df[["SKU", "Producto", "UXC", "Min_Alert", "Costo", "Nota_Alerta"]],
        column_config={
            "SKU": st.column_config.TextColumn("SKU", disabled=True),
            "Producto": st.column_config.TextColumn("Producto", disabled=True),
            "UXC": st.column_config.NumberColumn("Unidades por caja", min_value=1, step=1, format="%d"),
            "Costo": st.column_config.NumberColumn("Costo ($)", format="$ %.2f"),
            "Min_Alert": st.column_config.NumberColumn("Alerta Mín.")
        },
        width="stretch",
        hide_index=True
    )
    if st.button("💾 Guardar Parámetros", width="stretch"):
        # Actualizar df con los datos editados
        for _, row in cfg_edit.iterrows():
            df.loc[df["SKU"] == row["SKU"], ["UXC", "Min_Alert", "Costo", "Nota_Alerta"]] = [row["UXC"], row["Min_Alert"], row["Costo"], row["Nota_Alerta"]]
        save_data(df)
        st.success("✅ Parámetros guardados.")
        st.rerun()

    st.markdown("---")

    # 2. Gestión de Limpieza (Reset)
    st.markdown("### ⚠️ Zona de Limpieza")

    col_reset1, col_reset2 = st.columns(2)

    with col_reset1:
        st.markdown("**Limpieza Individual**")
        prod_to_reset = st.selectbox("Seleccionar producto para limpiar", [f"{r['SKU']} | {r['Producto']}" for _, r in df.iterrows()], key="reset_individual")
        confirm_ind = st.checkbox("Confirmar limpieza individual", key="check_ind")
        if st.button("🧹 Limpiar Cantidades Producto", type="primary", width="stretch"):
            if confirm_ind:
                sku_reset = prod_to_reset.split(" | ")[0]
                df.loc[df["SKU"] == sku_reset, ["Físico", "Por Recibir", "Reservado"]] = 0
                save_data(df)
                log_movement(sku_reset, "RESET INDIVIDUAL", 0, "Cantidades puestas a 0")
                st.success(f"✅ Cantidades de {sku_reset} reiniciadas.")
                st.rerun()
            else:
                st.warning("Debes marcar el checkbox de confirmación.")

    with col_reset2:
        st.markdown("**Reinicio Total**")
        st.write("Esto pondrá a 0 las cantidades de TODOS los productos. Acción irreversible.")
        usuario_reset = st.text_input("Usuario que reinicia", key="reset_usuario")
        confirma_reset = st.text_input("Escribe REINICIAR para habilitar", key="reset_texto")
        if st.button("🔥 REINICIAR TODO EL INVENTARIO", type="secondary", width="stretch"):
            if confirma_reset != "REINICIAR":
                st.error("Para reiniciar todo debes escribir exactamente REINICIAR.")
            elif not usuario_reset.strip():
                st.error("El usuario es obligatorio para registrar quién reinició.")
            else:
                df["Físico"] = 0
                df["Por Recibir"] = 0
                df["Reservado"] = 0
                save_data(df)
                log_movement("SISTEMA", "RESET TOTAL", 0, f"Inventario reiniciado por {usuario_reset.strip()}")
                st.success("✅ Todo el inventario ha sido reiniciado.")
                st.rerun()
