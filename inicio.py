import streamlit as st

# --- 1. CONFIGURACIÓN INDEPENDIENTE DE CADA PÁGINA ---

# Módulo Principal
portada = st.Page(
    "pages/0_portada.py", 
    title="Inicio / Portada", 
    icon="🌍", 
    default=True
)

# Bloque: Extracciones Parciales Estacionales
dato_icc_7_13 = st.Page(
    "pages/1_dato_lluvia_icc_7_13.py",
    title="Extracción ICC (07:00 a 13:00 hrs)",
    icon="📥"
)

dato_icc_13_18 = st.Page(
    "pages/2_dato_lluvia_icc_13_18.py",
    title="Extracción ICC (13:00 a 18:00 hrs)",
    icon="📥"
)

# Bloque: Matrices y Post-Procesamiento
matriz_dato_icc = st.Page(
    "pages/3_matriz_dato_ICC.py",
    title="Matriz: Archivo ICC",
    icon="📊"
)

matriz_dato_kobo = st.Page(
    "pages/4_matriz_dato_kobo.py",
    title="Matriz: KoboCollect",
    icon="📊"
)

mapa_parcial = st.Page(
    "pages/5_mapa_lluvias_parciales.py",
    title="Generación de Mapa Cartográfico",
    icon="🗺️"
)

# Bloque: Continuo Diario
extraccion_diario_ICC = st.Page(
    "pages/6_extraccion_dato_diario_ICC_.py", 
    title="Extracción ICC DIARIO REDMET", 
    icon="⚡"
)

extraccion_KOBO = st.Page(
    "pages/7_Dato_diario_kobo_consolidar.py", 
    title="Consolidación KOBOCOLLECT", 
    icon="⚡"
)

# Bloque: Pruebas y Laboratorio
pruebas_Kobo = st.Page(
    "pages/8_unificado_prueba.py", 
    title="Pruebas de archivos", 
    icon="🧪"
)

matriz_pivote = st.Page(
    "pages/9_prueba_2_pivote.py", 
    title="Matriz de archivo diario preliminar", 
    icon="📊"
)

DD_extra = st.Page(
    "pages/10_extraccion_kobo_dato_diario.py", 
    title="Extracción desde archivos de KoboCollect", 
    icon="⚡"
)

# --- 2. ESTILOS ---
ocultar_estilo = """
    <style>
    footer {visibility: hidden;}
    </style>
"""
st.markdown(ocultar_estilo, unsafe_allow_html=True)

# --- 3. CREACIÓN DE SUBCARPETAS EN EL MENÚ ---
navegacion_sihm = st.navigation(
    {
        "Módulo Principal": [portada],
        
        "📅 Datos Diarios Preliminares": [
            extraccion_diario_ICC,
            extraccion_KOBO,
            DD_extra,
            matriz_pivote,
            pruebas_Kobo
        ],
        
        "🌧️ Lluvias Parciales: Extracción": [
            dato_icc_7_13, 
            dato_icc_13_18
        ],
        
        "🛠️ Lluvias Parciales: Procesamiento": [
            matriz_dato_icc, 
            matriz_dato_kobo, 
            mapa_parcial
        ]
    }
)

# --- 4. EJECUCIÓN DE LA NAVEGACIÓN ---
navegacion_sihm.run()
