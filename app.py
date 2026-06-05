import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io
import re
import base64
import order_parsers  # Nuevo módulo para procesar PDFs de cadenas

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Gestión de Operaciones | Inventario ATP",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo CSS optimizado para ambos modos (Luz/Oscuro) y corrección de pestañas
st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        border-radius: 4px 4px 0px 0px;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(128, 128, 128, 0.1) !important;
    }
    [data-testid="stMetric"] {
        padding: 10px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        border_radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONSTANTES Y CARGA DE DATOS ---
DB_FILE = "inventario_data.csv"
HISTORY_FILE = "historial_movimientos.csv"
CONCILIATION_HISTORY = "historial_conciliaciones.csv"
SALES_HISTORY = "historial_ventas.csv"

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
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        if "Tránsito" in df.columns:
            df.rename(columns={"Tránsito": "Llegando a Bodega"}, inplace=True)
        # Asegurar que existan todas las columnas necesarias, incluyendo Costo
        for col in ["Min_Alert", "Nota_Alerta", "Costo"]:
            if col not in df.columns:
                df[col] = 10 if col == "Min_Alert" else (0.0 if col == "Costo" else "")

        # CORRECCIÓN: Asegurar que Nota_Alerta sea siempre texto y no tenga NaNs (evita error en data_editor)
        df["Nota_Alerta"] = df["Nota_Alerta"].fillna("").astype(str)

        df = df[["SKU", "Producto", "Físico", "Llegando a Bodega", "Comprometido", "Min_Alert", "Nota_Alerta", "Costo"]]
        return df
    else:
        data = [{"SKU": k, "Producto": v, "Físico": 0, "Llegando a Bodega": 0, "Comprometido": 0, "Min_Alert": 10, "Nota_Alerta": "", "Costo": 0.0} for k, v in CATALOGO.items()]
        return pd.DataFrame(data)

def save_data(df):
    df.to_csv(DB_FILE, index=False)

def log_movement(sku, tipo, cantidad, nota=""):
    entry = pd.DataFrame([{"Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "SKU": sku, "Tipo": tipo, "Cantidad": cantidad, "Nota": nota}])
    entry.to_csv(HISTORY_FILE, mode='a', header=not os.path.exists(HISTORY_FILE), index=False)

def log_conciliation(conciliation_df):
    conciliation_df["Fecha_Conciliacion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conciliation_df.to_csv(CONCILIATION_HISTORY, mode='a', header=not os.path.exists(CONCILIATION_HISTORY), index=False)

def log_sale(sku, cantidad, referencia=""):
    entry = pd.DataFrame([{
        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
        "SKU": sku, 
        "Producto": CATALOGO.get(sku, "Desconocido"),
        "Cantidad": cantidad, 
        "Referencia": referencia
    }])
    entry.to_csv(SALES_HISTORY, mode='a', header=not os.path.exists(SALES_HISTORY), index=False)

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
df["ATP"] = df["Físico"] + df["Llegando a Bodega"] - df["Comprometido"]

def calculate_status(row):
    if row["ATP"] <= 0: return "🔴 Agotado"
    if row["ATP"] <= row["Min_Alert"]: return "🟡 Crítico"
    return "🟢 Disponible"

df["Estado"] = df.apply(calculate_status, axis=1)

# --- SIDEBAR ---
st.sidebar.title("Operaciones")
st.sidebar.markdown("---")

with st.sidebar:
    metodo = st.radio("Método de Entrada", ["Individual", "Lote de Texto", "Importar Archivo"], label_visibility="collapsed")
    st.markdown("---")

    if metodo == "Individual":
        st.subheader("Registrar Movimiento")
        tipo = st.selectbox("Acción", ["Entrada de Fábrica", "Llegando a Bodega", "Venta / Orden", "Ajuste Directo"])
        prod_list = [f"{r['SKU']} | {r['Producto']}" for _, r in df.iterrows()]
        seleccion = st.selectbox("Producto", prod_list)
        sku = seleccion.split(" | ")[0]
        cantidad = st.number_input("Cantidad", step=1, value=0)
        nota = st.text_input("Nota / Referencia")
        
        if st.button("Ejecutar Registro", use_container_width=True):
            col = {"Entrada de Fábrica": "Físico", "Llegando a Bodega": "Llegando a Bodega", "Venta / Orden": "Comprometido", "Ajuste Directo": "Físico"}[tipo]
            if tipo == "Ajuste Directo":
                df.loc[df["SKU"] == sku, col] = cantidad
            else:
                df.loc[df["SKU"] == sku, col] += cantidad
            save_data(df)
            log_movement(sku, tipo, cantidad, nota)
            st.rerun()

    elif metodo == "Lote de Texto":
        st.subheader("Carga por Lote")
        st.caption("Formato: SKU, Cantidad")
        batch_input = st.text_area("Lista", height=150)
        tipo_batch = st.selectbox("Acción para el lote", ["Entrada de Fábrica", "Llegando a Bodega", "Venta / Orden"])
        if st.button("Procesar Lista", use_container_width=True):
            for line in batch_input.strip().split("\n"):
                try:
                    parts = line.replace(" ", "").split(",")
                    if len(parts) == 2:
                        s, c = parts
                        if s.upper() in df["SKU"].values:
                            col = {"Entrada de Fábrica": "Físico", "Llegando a Bodega": "Llegando a Bodega", "Venta / Orden": "Comprometido"}[tipo_batch]
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
st.header("Gestión de Inventario Disponible")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Stock Físico", int(df["Físico"].sum()))
m2.metric("Llegando a Bodega", int(df["Llegando a Bodega"].sum()))
m3.metric("Comprometido", int(df["Comprometido"].sum()))
m4.metric("Alertas", len(df[df["Estado"] != "🟢 Disponible"]))

st.markdown("---")

tab_inv, tab_fact, tab_ventas, tab_conc, tab_pre, tab_oc, tab_rep, tab_his, tab_est, tab_cfg = st.tabs(["INVENTARIO", "REGISTRAR FACTURACIÓN 🧾", "REPORTE DE VENTAS 📊", "CONCILIACIÓN 🔍", "PRE-VALIDACIÓN ✅", "ORDENES DE COMPRA 📄", "REPORTE DE COMPRA", "HISTORIAL", "ESTRATEGIA 📊", "CONFIGURACIÓN"])

with tab_inv:
    st.subheader("Control de Inventario")
    # Tabla editable para cambios rápidos
    df_editable = st.data_editor(
        df[["SKU", "Producto", "Físico", "Llegando a Bodega", "Comprometido", "ATP", "Estado", "Nota_Alerta"]],
        column_config={
            "SKU": st.column_config.TextColumn("SKU", disabled=True),
            "Producto": st.column_config.TextColumn("Producto", disabled=True),
            "ATP": st.column_config.NumberColumn("Disponible (ATP)", disabled=True, format="%d"),
            "Estado": st.column_config.TextColumn("Estado", disabled=True),
            "Físico": st.column_config.NumberColumn("Físico", format="%d"),
            "Llegando a Bodega": st.column_config.NumberColumn("En Tránsito", format="%d"),
            "Comprometido": st.column_config.NumberColumn("Comprometido", format="%d"),
            "Nota_Alerta": st.column_config.TextColumn("Observaciones")
        },
        use_container_width=True,
        hide_index=True,
        key="editor_inventario"
    )
    
    if st.button("💾 Guardar Cambios en Inventario", use_container_width=True):
        # Actualizar el dataframe original con los cambios del editor
        for index, row in df_editable.iterrows():
            sku = row["SKU"]
            df.loc[df["SKU"] == sku, ["Físico", "Llegando a Bodega", "Comprometido", "Nota_Alerta"]] = [row["Físico"], row["Llegando a Bodega"], row["Comprometido"], row["Nota_Alerta"]]
        save_data(df)
        st.success("✅ Inventario actualizado correctamente.")
        st.rerun()

with tab_fact:
    st.subheader("Registro Masivo de Facturación")
    st.info("Puedes pegar texto o subir múltiples PDFs de facturas. El sistema consolidará todo antes de descontar.")
    
    col_text, col_pdf = st.columns(2)
    
    with col_text:
        st.markdown("### ⌨️ Por Texto")
        fact_text = st.text_area("Pega aquí el detalle", height=150, placeholder="12.00 SHAMPOO ANA REGENEXT 400 ML. -", key="fact_area")
    
    with col_pdf:
        st.markdown("### 📄 Por PDF")
        fact_files = st.file_uploader("Subir Facturas (PDF)", type=["pdf"], accept_multiple_files=True)

    if st.button("🔍 Analizar y Consolidar Movimiento", use_container_width=True):
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
            res_data.append({"SKU": k, "Producto": CATALOGO.get(k, "Desconocido"), "Total": v})
        resumen_df = pd.DataFrame(res_data)
        st.table(resumen_df)
        
        if st.button("✅ CONFIRMAR Y RESTAR DE STOCK", type="primary", use_container_width=True):
            for sku, qty in st.session_state["consolidado_fact"].items():
                df.loc[df["SKU"] == sku, "Físico"] -= qty
                log_movement(sku, "FACTURACIÓN CONSOLIDADA", -qty, "Procesado múltiple")
                log_sale(sku, qty, "Carga Consolidada")
            
            save_data(df)
            st.success("🎉 Stock actualizado y ventas registradas.")
            del st.session_state["consolidado_fact"]
            st.rerun()

with tab_ventas:
    st.subheader("Análisis de Ventas (Facturado)")
    if os.path.exists(SALES_HISTORY):
        s_df = pd.read_csv(SALES_HISTORY)
        s_df["Fecha"] = pd.to_datetime(s_df["Fecha"])
        
        col_v1, col_v2 = st.columns([1, 2])
        
        with col_v1:
            st.markdown("### Top Productos")
            top_v = s_df.groupby("Producto")["Cantidad"].sum().sort_values(ascending=False)
            st.dataframe(top_v)
            
        with col_v2:
            st.markdown("### Ventas por Producto")
            st.bar_chart(top_v)
            
        st.markdown("### Historial Detallado")
        st.dataframe(s_df.sort_values(by="Fecha", ascending=False), use_container_width=True, hide_index=True)
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
            df['Producto_Norm'] = df['Producto'].str.upper().str.strip()
            match = df[df['Producto_Norm'] == prod_nom.upper()]
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
                    df.loc[df["SKU"] == sku_detectado, "Físico"] = nuevo_fisico
                    save_data(df.drop(columns=['Producto_Norm']))
                    log_df = pd.DataFrame([{"SKU": sku_detectado, "Producto": nombre_app, "Stock_Contifico": stock_contifico, "Fisico_Real": nuevo_fisico, "Diferencia": diferencia}])
                    log_conciliation(log_df)
                    log_movement(sku_detectado, "Conciliación", nuevo_fisico, f"Kardex: {kardex_file.name}")
                    st.rerun()
            else: st.error("Producto no encontrado.")

with tab_pre:
    st.subheader("Pre-validación de Facturas")
    pre_df = df[["SKU", "Producto", "ATP"]].copy()
    pre_df["Cantidad a Facturar"] = 0
    edited_pre = st.data_editor(pre_df, column_config={"ATP": st.column_config.NumberColumn("Disponible", disabled=True)}, hide_index=True, use_container_width=True)
    items_pedido = edited_pre[edited_pre["Cantidad a Facturar"] > 0].copy()
    if not items_pedido.empty:
        items_pedido["Alcanza"] = items_pedido.apply(lambda r: "🟢 SÍ" if r["ATP"] >= r["Cantidad a Facturar"] else "🔴 NO", axis=1)
        if all(items_pedido["Alcanza"] == "🟢 SÍ"): st.success("### ✅ PUEDES FACTURAR")
        else: st.error("### ❌ NO FACTURAR")
        st.dataframe(items_pedido[["SKU", "Producto", "ATP", "Cantidad a Facturar", "Alcanza"]], use_container_width=True, hide_index=True)

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
                
                oc_df = pd.DataFrame(items_oc)
                oc_df['SKU'] = oc_df['SKU'].str.upper().str.strip()
                
                # Unir con el inventario
                validation_df = oc_df.merge(df[["SKU", "Producto", "ATP", "Físico"]], on="SKU", how="left")
                
                # Calcular sugerencia de despacho
                def suggest_qty(row):
                    if pd.isna(row["ATP"]) or row["ATP"] <= 0: return 0
                    return min(int(row["Cantidad"]), int(row["ATP"]))

                validation_df["Sugerencia"] = validation_df.apply(suggest_qty, axis=1)
                validation_df["Estado_V"] = validation_df.apply(
                    lambda r: "🟢" if r["Sugerencia"] == r["Cantidad"] else ("🟡" if r["Sugerencia"] > 0 else "🔴"), 
                    axis=1
                )
                
                # Editor de despacho
                st.write("Ajusta las cantidades si es necesario antes de confirmar:")
                edited_oc = st.data_editor(
                    validation_df[["Estado_V", "Desc_Original", "Producto", "Cantidad", "ATP", "Sugerencia", "SKU"]],
                    column_config={
                        "Estado_V": st.column_config.TextColumn(" ", width="small"),
                        "Desc_Original": st.column_config.TextColumn("OC Original (Izquierda)", disabled=True),
                        "Producto": st.column_config.TextColumn("Sistema (Derecha)", disabled=True),
                        "Cantidad": st.column_config.NumberColumn("Pedido OC", disabled=True),
                        "ATP": st.column_config.NumberColumn("ATP", disabled=True),
                        "Sugerencia": st.column_config.NumberColumn("A Despachar", format="%d"),
                        "SKU": st.column_config.TextColumn("SKU", disabled=True)
                    },
                    use_container_width=True,
                    hide_index=True,
                    key="editor_oc"
                )
                
                if st.button("🚀 Confirmar Facturación y Restar de Físico", use_container_width=True, type="primary"):
                    items_processed = 0
                    for _, row in edited_oc.iterrows():
                        if row["Sugerencia"] > 0:
                            qty = int(row["Sugerencia"])
                            sku = row["SKU"]
                            df.loc[df["SKU"] == sku, "Físico"] -= qty
                            log_movement(sku, f"VENTA OC: {cadena}", -qty, f"OC Original: {row['Desc_Original'][:40]}")
                            items_processed += 1
                    
                    if items_processed > 0:
                        save_data(df)
                        st.success(f"✅ Se han facturado {items_processed} productos. El stock físico ha sido actualizado.")
                        st.rerun()
            else:
                st.error("No se pudieron extraer datos del PDF.")

with tab_rep:
    st.subheader("Necesidades de Reabastecimiento")
    rep_df = df[df["Estado"] != "🟢 Disponible"].copy()
    if not rep_df.empty:
        rep_df["Sugerencia"] = (rep_df["Min_Alert"] * 2) - rep_df["ATP"]
        st.table(rep_df[["SKU", "Producto", "ATP", "Estado", "Sugerencia"]])
    else: st.info("Todo optimizado.")

with tab_his:
    st.subheader("Análisis de Stock")
    st.bar_chart(df.set_index("Producto")["Físico"])
    st.markdown("---")
    if os.path.exists(HISTORY_FILE):
        st.dataframe(pd.read_csv(HISTORY_FILE).sort_values(by="Fecha", ascending=False), use_container_width=True, hide_index=True)

with tab_est:
    st.subheader("Reporte Ejecutivo y Estrategia")
    if os.path.exists(CONCILIATION_HISTORY):
        c_df = pd.read_csv(CONCILIATION_HISTORY)
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
        st.dataframe(c_df.sort_values(by="Fecha_Conciliacion", ascending=False), use_container_width=True, hide_index=True)
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
        use_container_width=True, 
        hide_index=True
    )
    if st.button("💾 Guardar Parámetros", use_container_width=True):
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
        if st.button("🧹 Limpiar Cantidades Producto", type="primary", use_container_width=True):
            if confirm_ind:
                sku_reset = prod_to_reset.split(" | ")[0]
                df.loc[df["SKU"] == sku_reset, ["Físico", "Llegando a Bodega", "Comprometido"]] = 0
                save_data(df)
                log_movement(sku_reset, "RESET INDIVIDUAL", 0, "Cantidades puestas a 0")
                st.success(f"✅ Cantidades de {sku_reset} reiniciadas.")
                st.rerun()
            else:
                st.warning("Debes marcar el checkbox de confirmación.")

    with col_reset2:
        st.markdown("**Reinicio Total**")
        st.write("Esto pondrá a 0 todas las cantidades de TODOS los productos.")
        confirm_all = st.checkbox("⚠️ CONFIRMAR REINICIO TOTAL", key="check_all")
        if st.button("🔥 REINICIAR TODO EL INVENTARIO", type="secondary", use_container_width=True):
            if confirm_all:
                df["Físico"] = 0
                df["Llegando a Bodega"] = 0
                df["Comprometido"] = 0
                save_data(df)
                log_movement("SISTEMA", "RESET TOTAL", 0, "Todo el inventario puesto a 0")
                st.success("✅ Todo el inventario ha sido reiniciado.")
                st.rerun()
            else:
                st.error("Acción cancelada. Debes confirmar con el checkbox.")
