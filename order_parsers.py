import pdfplumber
import pandas as pd
import re
import difflib

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


# --- LECTURA DE REPORTE DE BODEGA (captura de Excel: SKU | DESCRIPCIÓN | UM | SALDO) ---
# El SKU que usa bodega es distinto al SKU del catálogo de la app, así que se
# homologa por código. Si bodega agrega un código nuevo, cae al respaldo por
# descripción (get_sku_from_text).
WAREHOUSE_SKU_MAP = {
    "IECPANA0001": "AR001",
    "IECPANA0002": "AR002",
    "IECPANA0003": "AR003",
    "IECPANA0004": "AR004",
    "IECPANA0005": "AR007",
    "IECPANA0006": "AR005",
    "IECPANA0007": "AR006",
    "IELWANA0001": "ACP001",
    "IECPELX0022": "AE001",
    "IECPELX0023": "AE002",
    "IECPELX0024": "AE003",
}

# Ancla de inicio de fila: el código de SKU de bodega (ej. IECPANA0001).
# Todos los códigos reales tienen 11 caracteres; se acepta un rango (8-13)
# para tolerar que el OCR pierda o agregue algún carácter. Se exige además
# que parezca un código (tenga un dígito, o sea muy parecido a uno conocido)
# para no confundir palabras sueltas de la descripción (ej. "CRECIMIENTO").
_BODEGA_SKU_CODE = re.compile(r'\b([A-Z0-9]{8,13})\b')
# Dentro del tramo de texto de una fila, los últimos dos números son UM y Saldo
# (la descripción puede traer números intermedios, ej. "400 ML", "18 ML").
_BODEGA_TAIL_NUMS = re.compile(r'^(.*?)(\d{1,4})\s+([\d.,]+)\s*$')
# Respaldo: a veces el OCR solo logra leer un número de toda la fila (suele
# ser el Saldo, que es la columna más a la derecha y más contrastada).
_BODEGA_TAIL_ONE_NUM = re.compile(r'^(.*?)(\d[\d.,]*)\s*$')


def _code_similarity(token, code):
    return difflib.SequenceMatcher(None, token, code).ratio()


def _best_warehouse_code(token, cutoff=0.5):
    """Encuentra el código de bodega conocido más parecido a 'token'.
    Tolera errores típicos de OCR (I/J/¡/l confundidos, 0/O/D, 5/S, 8/B...).

    Si el token perdió justo el dígito que distingue a varios productos
    (ej. "IECPANA000X"), va a quedar igual de parecido a todos ellos. En ese
    caso es ambiguo y NO se adivina: mejor dejarlo sin resolver que asignar
    una cantidad al producto equivocado.
    """
    token = (token or "").upper().strip()
    if not token:
        return None
    ratios = sorted(
        ((c, _code_similarity(token, c)) for c in WAREHOUSE_SKU_MAP),
        key=lambda par: par[1],
        reverse=True,
    )
    mejor_codigo, mejor_ratio = ratios[0]
    if mejor_ratio < cutoff:
        return None
    if len(ratios) > 1 and abs(ratios[1][1] - mejor_ratio) < 1e-9:
        return None  # empate: ambiguo, no adivinar
    return mejor_codigo


def map_warehouse_sku(codigo_bodega, descripcion):
    codigo_bodega = (codigo_bodega or "").upper().strip()
    if codigo_bodega in WAREHOUSE_SKU_MAP:
        return WAREHOUSE_SKU_MAP[codigo_bodega]
    mejor = _best_warehouse_code(codigo_bodega)
    if mejor:
        return WAREHOUSE_SKU_MAP[mejor]
    return get_sku_from_text(descripcion or "")


def _looks_like_bodega_code(token):
    """¿Sirve este token como límite de fila? Umbral deliberadamente más
    bajo que el de map_warehouse_sku(): aquí solo se decide dónde corta una
    fila de otra (para no mezclar números de filas distintas), no a qué
    SKU corresponde. Filtra palabras sueltas de la descripción (ej.
    "CRECIMIENTO", "ACONDICIONADOR"), que quedan muy por debajo del umbral."""
    if any(ch.isdigit() for ch in token):
        return True
    mejor_ratio = max((_code_similarity(token, c) for c in WAREHOUSE_SKU_MAP), default=0)
    return mejor_ratio >= 0.45


def _preprocess_for_ocr(image):
    """Agranda, pasa a escala de grises y sube contraste antes del OCR.
    Tesseract falla mucho más en capturas de Excel pequeñas/comprimidas
    (ej. reenviadas por WhatsApp); esto ayuda bastante sin garantizar
    precisión perfecta."""
    from PIL import Image as PILImage, ImageOps

    resample = getattr(getattr(PILImage, "Resampling", PILImage), "LANCZOS")
    img = image.convert("L")
    lado_mayor = max(img.size)
    factor = 3 if lado_mayor < 1200 else (2 if lado_mayor < 2200 else 1)
    if factor > 1:
        img = img.resize((img.width * factor, img.height * factor), resample=resample)
    return ImageOps.autocontrast(img)


def parse_bodega_stock_image(file):
    """Lee una captura (foto/screenshot) del reporte de bodega vía OCR.

    Espera columnas tipo: SKU | DESCRIPCIÓN | UM | SALDO, donde SALDO ya
    viene en unidades totales (no cajas). No depende de que cada fila salga
    en una sola línea limpia: ancla cada fila por el código de SKU de bodega
    y toma todo el texto hasta el siguiente código como esa fila.

    Si el OCR no logra leer UM/Saldo de una fila (imagen borrosa), la fila
    se devuelve igual con esos campos en None en vez de descartarse en
    silencio, para que se pueda completar a mano en la revisión.

    Devuelve (items, no_reconocidos, texto_ocr_crudo) o
    (None, mensaje_error, "") si falta la dependencia de OCR.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return None, (
            "Falta el soporte de OCR (pytesseract/Pillow/tesseract-ocr). "
            "Revisa requirements.txt y packages.txt del proyecto."
        ), ""

    image = Image.open(file)
    try:
        image_proc = _preprocess_for_ocr(image)
    except Exception:
        image_proc = image

    try:
        texto = pytesseract.image_to_string(image_proc, config="--psm 6", lang="spa")
    except Exception:
        texto = pytesseract.image_to_string(image_proc, config="--psm 6")

    # Colapsa saltos de línea/espacios para no depender de cómo el OCR
    # partió cada fila.
    texto_plano = re.sub(r'\s+', ' ', texto.upper()).strip()

    matches = [m for m in _BODEGA_SKU_CODE.finditer(texto_plano) if _looks_like_bodega_code(m.group(1))]
    items = []
    no_reconocidos = []
    for i, m in enumerate(matches):
        codigo_bodega = m.group(1)
        inicio = m.end()
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(texto_plano)
        tramo = texto_plano[inicio:fin].strip()

        descripcion, um, saldo = tramo, None, None
        tail = _BODEGA_TAIL_NUMS.match(tramo)
        if tail:
            desc_candidata, um_str, saldo_str = tail.groups()
            try:
                um = int(um_str)
                saldo = int(float(saldo_str.replace(",", "")))
                descripcion = desc_candidata
            except ValueError:
                um, saldo = None, None
        if saldo is None:
            # Respaldo: el OCR solo trajo un número en esta fila (probablemente
            # el Saldo). UM queda en None para completarlo a mano en la revisión.
            tail_uno = _BODEGA_TAIL_ONE_NUM.match(tramo)
            if tail_uno:
                desc_candidata, saldo_str = tail_uno.groups()
                try:
                    saldo = int(float(saldo_str.replace(",", "")))
                    descripcion = desc_candidata
                except ValueError:
                    saldo = None

        sku_app = map_warehouse_sku(codigo_bodega, descripcion)
        item = {
            "SKU_Bodega": codigo_bodega,
            "Descripcion": descripcion.strip(),
            "UM": um,
            "Saldo": saldo,
            "SKU": sku_app,
        }
        (items if sku_app else no_reconocidos).append(item)

    return items, no_reconocidos, texto
