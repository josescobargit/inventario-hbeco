import pdfplumber
import pandas as pd
import re

# --- CONFIGURACIÓN DE EMPAQUE (UXC) ---
UXC_MAP = {
    "AE001": 12,
    "AE002": 12,
    "AE003": 6,   
    "AR001": 12,
    "AR002": 12,
    "AR003": 12,
    "AR004": 12,
    "AR007": 12,
    "ACP001": 12,
}

# Todos los SKU del catálogo (incluye sachets AR005/AR006 que no tienen UXC).
KNOWN_SKUS = [
    "ACP001", "AE001", "AE002", "AE003",
    "AR001", "AR002", "AR003", "AR004",
    "AR005", "AR006", "AR007",
]

def get_sku_from_text(text):
    text = text.upper()

    # 1. Prioridad Absoluta: Buscar mención directa de SKU (todo el catálogo)
    for sku in KNOWN_SKUS:
        if sku in text: return sku

    # 2. Prioridad de Producto: El PACK (AE003) y TRATAMIENTO (AR003)
    if any(k in text for k in ["PACK", "X2", "SHAMP + ACONDIC", "SHA+ACO"]):
        return "AE003"

    # El tratamiento en Favorita viene como "ANA TRATAMIENTO CAPILA" (sin la palabra REGENEXT)
    if "TRATAMIENTO" in text and ("CAPILA" in text or "CAPILAR" in text):
        return "AR003"

    # Sachets 18 ML (AR005 shampoo / AR006 acondicionador). Va antes de REGENEXT
    # porque también son línea Regenext y si no caerían en AR001/AR002.
    if "SACHET" in text or "18 ML" in text or "18ML" in text:
        if "ACOND" in text: return "AR006"
        if "SHAMPOO" in text or "SH " in text: return "AR005"

    # 3. Línea REGENEXT
    if "REGENEXT" in text:
        if "SHAMPOO" in text: return "AR001"
        if "ACOND" in text: return "AR002"
        if "CREMA" in text: return "AR004"
        return "AR001"
        
    # 4. Línea ELIXIR / ESSENTIAL
    if "ELIXIR" in text or "ESSENTIAL" in text or "370" in text or "CRECIMIENTO" in text:
        if "SHAMPOO" in text: return "AE001"
        if "ACOND" in text or "ACONDION" in text: return "AE002"
        return "AE001"
        
    # 5. Otros
    if "BABY" in text: return "AR007"
    if "TOALLITAS" in text: return "ACP001"
    
    return None

def parse_tia(file):
    with pdfplumber.open(file) as pdf:
        all_text = ""
        for page in pdf.pages: all_text += (page.extract_text() or "") + "\n"
        all_text = all_text.upper()
        homologation_map = {}
        for sku in UXC_MAP.keys():
            match = re.search(r'(\d+)\s+([A-Z\s\d]+?)\s+\d{10,}\s+(' + sku + r')', all_text)
            if match:
                tia_desc = match.group(2).strip()
                homologation_map[tia_desc] = sku
        results = []
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables: continue
            for table in tables:
                for row in table:
                    if not row or len(row) < 8: continue
                    cant_cell = str(row[0]).strip()
                    if cant_cell.isdigit() and int(cant_cell) > 0 and int(cant_cell) < 10000:
                        if len(row) > 6 and row[6]:
                            prod_desc = str(row[6]).upper().strip()
                            sku = homologation_map.get(prod_desc)
                            if not sku: sku = get_sku_from_text(prod_desc)
                            if sku:
                                results.append({"Orden": "TIA", "SKU": sku, "Cantidad": int(cant_cell), "Desc_Original": prod_desc})
        if results:
            df_tia = pd.DataFrame(results).sort_values("Cantidad", ascending=False).drop_duplicates("SKU")
            return df_tia.to_dict('records')
        return results

def parse_favorita(file):
    with pdfplumber.open(file) as pdf:
        results = []
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            for line in text.split("\n"):
                line = line.upper()
                sku = get_sku_from_text(line)
                if sku:
                    nums = re.findall(r'\d+\.\d+|\d+', line)
                    if nums:
                        cajas_pedidas = int(float(nums[-1]))
                        uxc = UXC_MAP.get(sku, 12)
                        results.append({"Orden": "FAVORITA", "SKU": sku, "Cantidad": cajas_pedidas * uxc, "Desc_Original": line})
        return results

def parse_gerardo_ortiz(file):
    with pdfplumber.open(file) as pdf:
        results = []
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            for line in text.split("\n"):
                line = line.upper()
                sku = get_sku_from_text(line)
                if sku:
                    is_case = "-CJ" in line or " CAJA " in line
                    parts = line.split()
                    qty = None
                    for i, part in enumerate(parts):
                        if "X900" in part or "-UN" in part or "-CJ" in part:
                            if i + 1 < len(parts):
                                clean_val = re.sub(r'[^\d]', '', parts[i+1])
                                if clean_val:
                                    qty = int(clean_val)
                                    if is_case: qty = qty * UXC_MAP.get(sku, 12)
                                    break
                    if qty is None and len(parts) >= 3:
                        nums = [p for p in parts if p.replace(".", "").replace(",", "").isdigit()]
                        if len(nums) >= 3:
                            qty = int(float(nums[-3].replace(",", ".")))
                    if sku and qty is not None:
                        results.append({"Orden": "GO", "SKU": sku, "Cantidad": qty, "Desc_Original": line})
        return results

def parse_rosado(file):
    with pdfplumber.open(file) as pdf:
        results = []
        current_order = "S/N"
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            lines = text.split("\n")
            for line in lines:
                line = line.upper()
                if "NUMERO DE ORDEN" in line:
                    order_match = re.search(r'NUMERO DE ORDEN\s+(\d+)', line)
                    if order_match: current_order = order_match.group(1)
                sku = get_sku_from_text(line)
                if sku:
                    parts = line.split()
                    uxc = None
                    qty = None
                    for i, part in enumerate(parts):
                        if part.isdigit() and int(part) in [6, 12, 24]:
                            uxc = int(part)
                            if i + 1 < len(parts):
                                q_str = parts[i+1]
                                if "," in q_str:
                                    qty = float(q_str.replace(",", "."))
                                    break
                    if not uxc: uxc = UXC_MAP.get(sku, 12)
                    if sku and qty is not None:
                        results.append({"Orden": current_order, "SKU": sku, "Cantidad": int(qty * uxc), "Desc_Original": line})
        return results

def parse_danec(file):
    with pdfplumber.open(file) as pdf:
        results = []
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            for line in text.split("\n"):
                line = line.upper()
                sku = get_sku_from_text(line)
                if sku:
                    is_case = " UN " not in line and (" CJ " in line or " CAJA " in line)
                    match = re.search(r'(\d+\.\d+|\d+)', line)
                    if match:
                        qty = float(match.group(1))
                        total_qty = int(qty * (UXC_MAP.get(sku, 12) if is_case else 1))
                        results.append({"Orden": "DANEC", "SKU": sku, "Cantidad": total_qty, "Desc_Original": line})
        return results

def detect_chain_and_parse(file):
    with pdfplumber.open(file) as pdf:
        text = ""
        for page in pdf.pages: text += (page.extract_text() or "").upper() + "\n"
        if "TIENDAS INDUSTRIALES ASOCIADAS" in text or "TIA S.A." in text: return "TIA", parse_tia(file)
        if "CORPORACION FAVORITA" in text or "FAVORITA" in text: return "FAVORITA", parse_favorita(file)
        if "GERARDO ORTIZ" in text: return "GERARDO ORTIZ", parse_gerardo_ortiz(file)
        if "INDUSTRIAL DANEC" in text: return "DANEC", parse_danec(file)
        if "CORPORACION EL ROSADO" in text or "EL ROSADO" in text: return "EL ROSADO", parse_rosado(file)
    return "DESCONOCIDA", None
