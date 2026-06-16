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

def load_data():
    return storage.load_inventory(CATALOGO, DB_FILE)

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

# --- SIDEBAR ---
st.sidebar.title("Operaciones")
st.sidebar.caption(f"Persistencia: {storage.storage_label()}")
st.sidebar.caption(f"Hora local: {storage.now_display()} ({storage.timezone_label()})")
st.sidebar.markdown("---")

with st.sidebar:
    metodo = st.radio("Método de Entrada", ["Individual", "Lote de Texto", "Importar Archivo"], label_visibility="collapsed")
    st.markdown("---")

    if metodo == "Individual":
        st.subheader("Registrar Movimiento")
        tipo = st.selectbox("Acción", ["Entrada de Fábrica", "Por Recibir", "Reservar", "Liberar Reserva", "Ajuste Directo"])
        prod_list = [f"{r['SKU']} | {r['Producto']}" for _, r in df.iterrows()]
        seleccion = st.selectbox("Producto", prod_list)
        sku = seleccion.split(" | ")[0]
        cantidad = st.number_input("Cantidad", step=1, value=0)
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

tab_inv, tab_fact, tab_ventas, tab_conc, tab_pre, tab_oc, tab_rep, tab_his, tab_est, tab_cfg = st.tabs(["Inventario", "Facturación", "Ventas", "Conciliación", "Pre-validación", "Órdenes", "Compras", "Historial", "Estrategia", "Config."])

with tab_inv:
    st.subheader("Control de Inventario")
    # Tabla editable para cambios rápidos
    df_editable = st.data_editor(
        df[["SKU", "Producto", "Físico", "Reservado", "Disponible", "Por Recibir", "Estado", "Nota_Alerta"]],
        column_config={
            "SKU": st.column_config.TextColumn("SKU", disabled=True),
            "Producto": st.column_config.TextColumn("Producto", disabled=True),
            "Disponible": st.column_config.NumberColumn("Disponible", disabled=True, format="%d"),
            "Estado": st.column_config.TextColumn("Estado", disabled=True),
            "Físico": st.column_config.NumberColumn("Físico", format="%d"),
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

with tab_fact:
    st.subheader("Registro de Facturación")
    st.info("La factura descuenta stock físico y queda registrada por número para trazabilidad y anulación.")
    meta1, meta2, meta3, meta4 = st.columns(4)
    numero_factura = meta1.text_input("Número de factura")
    cliente_factura = meta2.text_input("Cliente / Cadena")
    oc_factura = meta3.text_input("OC relacionada")
    usuario_factura = meta4.text_input("Usuario")
    
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
            res_data.append({
                "SKU": k,
                "Producto": CATALOGO.get(k, "Desconocido"),
                "Total": v,
                "Disponible": disponible,
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

with tab_conc:
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

with tab_pre:
    st.subheader("Pre-validación de Facturas")
    pre_df = df[["SKU", "Producto", "Disponible"]].copy()
    pre_df["Cantidad a Facturar"] = 0
    edited_pre = st.data_editor(pre_df, column_config={"Disponible": st.column_config.NumberColumn("Disponible", disabled=True)}, hide_index=True, width="stretch")
    items_pedido = edited_pre[edited_pre["Cantidad a Facturar"] > 0].copy()
    if not items_pedido.empty:
        items_pedido["Alcanza"] = items_pedido.apply(lambda r: "🟢 SÍ" if r["Disponible"] >= r["Cantidad a Facturar"] else "🔴 NO", axis=1)
        if all(items_pedido["Alcanza"] == "🟢 SÍ"): st.success("### ✅ PUEDES FACTURAR")
        else: st.error("### ❌ NO FACTURAR")
        st.dataframe(items_pedido[["SKU", "Producto", "Disponible", "Cantidad a Facturar", "Alcanza"]], width="stretch", hide_index=True)

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
                validation_df = oc_df.merge(df[["SKU", "Producto", "Disponible", "Físico"]], on="SKU", how="left")
                
                # Calcular sugerencia de despacho
                def suggest_qty(row):
                    if pd.isna(row["Disponible"]) or row["Disponible"] <= 0: return 0
                    return min(int(row["Cantidad"]), int(row["Disponible"]))

                validation_df["Sugerencia"] = validation_df.apply(suggest_qty, axis=1)
                validation_df["Estado_V"] = validation_df.apply(
                    lambda r: "🟢" if r["Sugerencia"] == r["Cantidad"] else ("🟡" if r["Sugerencia"] > 0 else "🔴"), 
                    axis=1
                )
                
                # Editor de despacho
                st.write("Ajusta las cantidades si es necesario antes de confirmar:")
                edited_oc = st.data_editor(
                    validation_df[["Estado_V", "Desc_Original", "Producto", "Cantidad", "Disponible", "Sugerencia", "SKU"]],
                    column_config={
                        "Estado_V": st.column_config.TextColumn(" ", width="small"),
                        "Desc_Original": st.column_config.TextColumn("OC Original (Izquierda)", disabled=True),
                        "Producto": st.column_config.TextColumn("Sistema (Derecha)", disabled=True),
                        "Cantidad": st.column_config.NumberColumn("Pedido OC", disabled=True),
                        "Disponible": st.column_config.NumberColumn("Disponible", disabled=True),
                        "Sugerencia": st.column_config.NumberColumn("A Despachar", format="%d"),
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

with tab_rep:
    st.subheader("Necesidades de Reabastecimiento")
    rep_df = df[df["Estado"] != "🟢 Disponible"].copy()
    if not rep_df.empty:
        rep_df["Sugerencia"] = (rep_df["Min_Alert"] * 2) - rep_df["Disponible"]
        st.table(rep_df[["SKU", "Producto", "Disponible", "Estado", "Sugerencia"]])
    else: st.info("Todo optimizado.")

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

with tab_cfg:
    st.subheader("Configuración de Sistema")
    
    # 1. Edición de Parámetros
    st.markdown("### 🛠️ Parámetros de Productos")
    cfg_edit = st.data_editor(
        df[["SKU", "Producto", "Min_Alert", "Costo", "Nota_Alerta"]], 
        column_config={
            "SKU": st.column_config.TextColumn("SKU", disabled=True),
            "Producto": st.column_config.TextColumn("Producto", disabled=True),
            "Costo": st.column_config.NumberColumn("Costo ($)", format="$ %.2f"),
            "Min_Alert": st.column_config.NumberColumn("Alerta Mín.")
        }, 
        width="stretch", 
        hide_index=True
    )
    if st.button("💾 Guardar Parámetros", width="stretch"):
        # Actualizar df con los datos editados
        for _, row in cfg_edit.iterrows():
            df.loc[df["SKU"] == row["SKU"], ["Min_Alert", "Costo", "Nota_Alerta"]] = [row["Min_Alert"], row["Costo"], row["Nota_Alerta"]]
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
