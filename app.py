import streamlit as st
import requests
import pandas as pd
import html
from io import BytesIO
import datetime
import docx
from docx import Document
from docx.shared import Pt

# ==========================================
# CONFIGURACIÓN INICIAL Y ESTILOS
# ==========================================
st.set_page_config(page_title="Boletín Mensual - Banxico", layout="wide")

# Inyección de CSS para cambiar el color al Azul Banxico (#00205B)
st.markdown("""
    <style>
    /* Estilo para los botones principales y de descarga */
    div.stButton > button, div.stDownloadButton > button {
        background-color: #00205B !important;
        color: white !important;
        border: none !important;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        background-color: #00153D !important;
        color: white !important;
    }
    /* Estilo para las etiquetas (tags) de los selectores múltiples (meses y años) */
    span[data-baseweb="tag"] {
        background-color: #00205B !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# FUNCIONES AUXILIARES (BACKEND)
# ==========================================

@st.cache_data(show_spinner="Descargando y procesando datos del BIS...")
def load_data_bis():
    url = "https://www.bis.org/api/document_lists/cbspeeches.json"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    speeches_dict = data.get("list", {})
    rows = []

    for path, speech in speeches_dict.items():
        title = html.unescape(speech.get("short_title", ""))
        date_str = speech.get("publication_start_date", "")

        link = "https://www.bis.org" + path + (".htm" if not path.endswith(".htm") else "")

        rows.append({
            "Date": date_str,
            "Title": title,
            "Link": link
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date", ascending=False)
    
    return df

def add_hyperlink(paragraph, text, url):
    part = paragraph.part
    r_id = part.relate_to(url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)

    hyperlink = docx.oxml.shared.OxmlElement('w:hyperlink')
    hyperlink.set(docx.oxml.shared.qn('r:id'), r_id)

    new_run = docx.oxml.shared.OxmlElement('w:r')
    rPr = docx.oxml.shared.OxmlElement('w:rPr')

    # Color Azul
    c = docx.oxml.shared.OxmlElement('w:color')
    c.set(docx.oxml.shared.qn('w:val'), '0000EE')
    rPr.append(c)

    # Subrayado
    u = docx.oxml.shared.OxmlElement('w:u')
    u.set(docx.oxml.shared.qn('w:val'), 'single')
    rPr.append(u)

    # Formato: Negrita
    b = docx.oxml.shared.OxmlElement('w:b')
    rPr.append(b)

    # Formato: Tamaño 12 (en la librería se mide en medios puntos, por lo que 24 = 12pt)
    sz = docx.oxml.shared.OxmlElement('w:sz')
    sz.set(docx.oxml.shared.qn('w:val'), '24')
    rPr.append(sz)
    
    # Asegurar el tamaño también para caracteres complejos
    szCs = docx.oxml.shared.OxmlElement('w:szCs')
    szCs.set(docx.oxml.shared.qn('w:val'), '24')
    rPr.append(szCs)

    # Formato: Fuente Calibri
    rFonts = docx.oxml.shared.OxmlElement('w:rFonts')
    rFonts.set(docx.oxml.shared.qn('w:ascii'), 'Calibri')
    rFonts.set(docx.oxml.shared.qn('w:hAnsi'), 'Calibri')
    rPr.append(rFonts)

    t = docx.oxml.shared.OxmlElement('w:t')
    t.text = text
    new_run.append(rPr)
    new_run.append(t)
    
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink

def generate_word(dataframe, title="Discursos"):
    doc = Document()
    doc.add_heading(title, 0)

    # Tabla sin bordes
    table = doc.add_table(rows=1, cols=2)
    
    # Encabezados con formato Calibri 12 Negrita
    hdr_cells = table.rows[0].cells
    for idx, header_text in enumerate(['Date', 'Title']):
        p = hdr_cells[idx].paragraphs[0]
        run = p.add_run(header_text)
        run.font.name = 'Calibri'
        run.font.size = Pt(12)
        run.bold = True

    # Llenado de datos
    for index, row in dataframe.iterrows():
        row_cells = table.add_row().cells
        
        # Eliminar los "00:00:00" extrayendo solo los 10 primeros caracteres (YYYY-MM-DD)
        date_str = str(row['Date'])[:10]
        
        # Celda 1: Fecha (Aplicamos Calibri 12 Negrita)
        p_date = row_cells[0].paragraphs[0]
        run_date = p_date.add_run(date_str)
        run_date.font.name = 'Calibri'
        run_date.font.size = Pt(12)
        run_date.bold = True
        
        # Celda 2: Título (El formato se inyecta por dentro de add_hyperlink)
        p_title = row_cells[1].paragraphs[0]
        add_hyperlink(p_title, str(row['Title']), str(row['Link']))

    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return output
# ==========================================
# INTERFAZ DE USUARIO (SIDEBAR Y NAVEGACIÓN)
# ==========================================

# 1. Logo institucional en la barra lateral
try:
    st.sidebar.image("logo_banxico.png", use_column_width=True)
except:
    st.sidebar.markdown("### 🏦 BANCO DE MÉXICO")

st.sidebar.markdown("---")
st.sidebar.header("Menú de Navegación")

# 2. Selector de Tipo de Documento
tipo_doc = st.sidebar.selectbox(
    "Selecciona el Tipo de Documento",
    ["Reportes", "Publicaciones Institucionales", "Investigación", "Discursos"]
)

# 3. Selector de Organismo (Listas exactas basadas en tus imágenes)
if tipo_doc == "Discursos":
    organismos = [
        "BBk (Alemania)", "BdE (España)", "BdF (Francia)", "BM", 
        "BoC (Canadá)", "BoE (Inglaterra)", "BoJ (Japón)", "BPI", 
        "CEF", "ECB (Europa)", "Fed (Estados Unidos)", "FMI", "PBoC (China)"
    ]
elif tipo_doc == "Reportes":
    organismos = ["BID", "BM", "BPI", "CEF", "FEM", "OCDE"]
elif tipo_doc == "Investigación":
    organismos = ["BID", "BM", "BPI", "CEMLA", "FMI", "OCDE"]
elif tipo_doc == "Publicaciones Institucionales":
    organismos = ["BM", "BPI", "CEF", "CEMLA", "FMI", "G20", "OCDE", "OEI"]

organismo_seleccionado = st.sidebar.selectbox("Selecciona el Organismo", organismos)

st.sidebar.markdown("---")
st.sidebar.info("Herramienta de extracción automatizada para la elaboración del boletín mensual.")


# ==========================================
# CONTENIDO PRINCIPAL (MAIN PAGE)
# ==========================================

st.title("Boletín Mensual de Organismos Internacionales")
st.markdown(f"**Explorador de {tipo_doc} - {organismo_seleccionado}**")
st.markdown("---")

# ==========================================
# MÓDULOS DE EXTRACCIÓN
# ==========================================

# MÓDULO: DISCURSOS -> BPI (Antes BIS)
if tipo_doc == "Discursos" and organismo_seleccionado == "BPI":
    
    st.subheader("1. Selecciona el Mes y Año")
    df = load_data_bis()

    anios_disponibles = df["Date"].dt.year.dropna().unique().tolist()
    anios_disponibles.sort(reverse=True)
    anios_str = [str(int(a)) for a in anios_disponibles]

    if "2026" in anios_str:
        anios_str.remove("2026")
        anios_str.insert(0, "2026")

    meses_dict = {
        "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4,
        "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8,
        "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
    }

    col1, col2 = st.columns(2)
    with col1:
        meses_seleccionados = st.multiselect(
            "Mes(es)",
            options=list(meses_dict.keys()),
            default=[] 
        )
    with col2:
        anios_seleccionados = st.multiselect(
            "Año(s)",
            options=anios_str,
            default=["2026"] if "2026" in anios_str else []
        )

    buscar = st.button("🔍 Buscar", type="primary")

    if buscar or "bis_df_filtrado" in st.session_state:
        
        if not meses_seleccionados or not anios_seleccionados:
            st.warning("⚠️ Por favor, selecciona al menos un mes y un año para realizar la búsqueda.")
        else:
            meses_num = [meses_dict[m] for m in meses_seleccionados]
            anios_num = [int(a) for a in anios_seleccionados]
            
            mask = (df["Date"].dt.year.isin(anios_num)) & (df["Date"].dt.month.isin(meses_num))
            filtered_df = df[mask]
            
            st.session_state["bis_df_filtrado"] = filtered_df

            if len(filtered_df) > 0:
                st.subheader("2. Resultados de la búsqueda")
                
                # Columnas para el mensaje de éxito y el botón de descarga
                col_mensaje, col_boton = st.columns([3, 1])
                
                with col_mensaje:
                    str_meses = ", ".join(meses_seleccionados)
                    str_anios = ", ".join(anios_seleccionados)
                    st.success(f"Se encontraron **{len(filtered_df)}** discursos en **{str_meses} {str_anios}**.")
                
                with col_boton:
                    word_file = generate_word(filtered_df, title="BIS Central Bank Speeches")
                    st.download_button(
                        label="📄 Descargar en Word",
                        data=word_file,
                        file_name=f"bis_speeches_{'_'.join(meses_seleccionados)}_{'_'.join(anios_seleccionados)}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
                
                # Procesar y mostrar la tabla en pantalla
                filtered_df_display = filtered_df.copy()
                filtered_df_display["Date"] = filtered_df_display["Date"].dt.strftime('%Y-%m-%d')
                filtered_df_display["Title"] = filtered_df_display.apply(
                    lambda x: f"[{x['Title']}]({x['Link']})", axis=1
                )

                st.markdown(
                    filtered_df_display[["Date", "Title"]].to_markdown(index=False),
                    unsafe_allow_html=True
                )

            else:
                st.warning("No hay discursos del BIS para las fechas seleccionadas. Intenta con otro mes.")
    else:
        st.info("👆 Selecciona el mes y año arriba y presiona **'Buscar'**.")

# MÓDULOS EN CONSTRUCCIÓN (Placeholder para el resto del menú)
else:
    st.info(f"El extractor de **{tipo_doc}** para **{organismo_seleccionado}** está en construcción.")
    st.write("Próximamente podrás extraer estos documentos de forma automatizada.")


