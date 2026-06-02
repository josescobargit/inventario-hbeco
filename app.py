import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io
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

tab_inv, tab_conc, tab_pre, tab_oc, tab_rep, tab_his, tab_est, tab_cfg = st.tabs(["INVENTARIO", "CONCILIACIÓN 🔍", "PRE-VALIDACIÓN ✅", "ORDENES DE COMPRA 📄", "REPORTE DE COMPRA", "HISTORIAL", "ESTRATEGIA 📊", "CONFIGURACIÓN"])

with tab_inv:
    st.dataframe(
        df[["SKU", "Producto", "Físico", "Llegando a Bodega", "Comprometido", "ATP", "Estado", "Nota_Alerta"]],
        column_config={
            "SKU": st.column_config.TextColumn("SKU", width="small"),
            "Producto": st.column_config.TextColumn("Producto", width="large"),
            "ATP": st.column_config.NumberColumn("Disponible", format="%d"),
            "Estado": st.column_config.TextColumn("Estado", width="medium"),
            "Físico": st.column_config.NumberColumn("Físico", format="%d"),
            "Nota_Alerta": st.column_config.TextColumn("Observaciones", width="medium")
        },
        use_container_width=True,
        hide_index=True
    )

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
    st.info("Sube la OC de la cadena (TIA, FAVORITA, DANEC, GERARDO ORTIZ) para verificar stock y facturación.")
    
    oc_file = st.file_uploader("Subir PDF de Orden de Compra", type=["pdf"])
    
    if oc_file:
        cadena, items_oc = order_parsers.detect_chain_and_parse(oc_file)
        
        if items_oc:
            st.success(f"✅ OC Detectada: **{cadena}**")
            
            # Convertir a DataFrame para comparar
            oc_df = pd.DataFrame(items_oc)
            
            # Unir con el inventario actual
            # Normalizamos SKUs para el cruce
            oc_df['SKU'] = oc_df['SKU'].str.upper().str.strip()
            
            # Traer nombres y ATP del sistema
            validation_df = oc_df.merge(df[["SKU", "Producto", "ATP"]], on="SKU", how="left")
            
            # Si no encontró el SKU por código, podría ser un SKU que no tenemos o error de parseo
            if validation_df["Producto"].isnull().any():
                st.warning("⚠️ Algunos SKUs de la OC no fueron reconocidos en el sistema.")
            
            validation_df["Alcanza"] = validation_df.apply(lambda r: "🟢 SÍ" if pd.notnull(r["ATP"]) and r["ATP"] >= r["Cantidad"] else "🔴 NO", axis=1)
            
            puedo_facturar_oc = all(validation_df["Alcanza"] == "🟢 SÍ")
            
            if puedo_facturar_oc:
                st.success(f"### ✅ FACTURABLE: La OC de {cadena} puede procesarse completa.")
            else:
                st.error(f"### ❌ NO FACTURABLE: Hay faltantes para esta OC.")
            
            # Mostrar por Orden si hay más de una (como en El Rosado)
            ordenes_unicas = validation_df["Orden"].unique()
            if len(ordenes_unicas) > 1 or (len(ordenes_unicas) == 1 and ordenes_unicas[0] != cadena):
                for ord_num in ordenes_unicas:
                    with st.expander(f"Orden Nº {ord_num}", expanded=True):
                        ord_df = validation_df[validation_df["Orden"] == ord_num]
                        st.dataframe(
                            ord_df[["SKU", "Producto", "Cantidad", "ATP", "Alcanza"]],
                            column_config={
                                "Cantidad": st.column_config.NumberColumn("Pedida"),
                                "ATP": st.column_config.NumberColumn("Disponible (ATP)"),
                            },
                            use_container_width=True,
                            hide_index=True
                        )
            else:
                st.dataframe(
                    validation_df[["SKU", "Producto", "Cantidad", "ATP", "Alcanza"]],
                    column_config={
                        "Cantidad": st.column_config.NumberColumn("Pedida en OC"),
                        "ATP": st.column_config.NumberColumn("Disponible (ATP)"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
            
            # Botón para descargar resumen de validación
            buffer_oc = io.BytesIO()
            with pd.ExcelWriter(buffer_oc, engine='xlsxwriter') as writer:
                validation_df.to_excel(writer, index=False, sheet_name='Validacion_OC')
            
            st.download_button(
                label="📥 Descargar Reporte de Validación OC (XLSX)",
                data=buffer_oc.getvalue(),
                file_name=f"validacion_OC_{cadena}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            if cadena == "DESCONOCIDA":
                st.error("❌ No se reconoció el formato de esta OC. Cadenas soportadas: TIA, FAVORITA, DANEC, GERARDO ORTIZ.")
                st.info("💡 Si es de EL ROSADO, por favor envíame un ejemplo para entrenar al sistema.")
            else:
                st.error(f"❌ No se pudieron extraer ítems de la OC de {cadena}. Verifica que el PDF sea legible.")

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
    st.subheader("Configuración")
    cfg_edit = st.data_editor(df[["SKU", "Producto", "Min_Alert", "Costo", "Nota_Alerta"]], column_config={"Costo": st.column_config.NumberColumn("Costo ($)", format="$ %.2f")}, use_container_width=True, hide_index=True)
    if st.button("Guardar Parámetros"):
        df["Min_Alert"] = cfg_edit["Min_Alert"]; df["Costo"] = cfg_edit["Costo"]; df["Nota_Alerta"] = cfg_edit["Nota_Alerta"]
        save_data(df); st.success("Guardado."); st.rerun()
    if st.button("REINICIAR TODO", type="secondary"):
        if st.checkbox("Confirmar reinicio"):
            df["Físico"] = 0; df["Llegando a Bodega"] = 0; df["Comprometido"] = 0; df["Costo"] = 0.0
            save_data(df); st.rerun()
