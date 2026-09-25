import streamlit as st

# --- 1. CONFIGURACIÓN INDEPENDIENTE DE CADA PÁGINA ---
# Validado exactamente contra la estructura física de tu repositorio

portada = st.Page(
    "pages/0_portada.py", 
    title="Inicio / Portada", 
    icon="🌍", 
    default=True
)
ocultar_estilo = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(ocultar_estilo, unsafe_allow_html=True)

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

# Bloque: Continuo Diario (¡Agregado correctamente!)
extraccion_diario = st.Page(
    "pages/6_extraccion_dato_diario_ICC_.py", 
    title="Extracción ICC DIARIO REDMET", 
    icon="⚡"
)


# --- 2. CREACIÓN DE SUBCARPETAS INTELIGENTES EN EL MENÚ ---
navegacion_sihm = st.navigation(
    {
        "Módulo Principal": [portada],
        "命 Lluvias Parciales: Extracción": [
            dato_icc_7_13, 
            dato_icc_13_18
        ],
        "🛠️ Lluvias Parciales: Procesamiento": [
            matriz_dato_icc, 
            matriz_dato_kobo, 
            mapa_parcial
        ],
        "📅 Monitoreo Continuo": [
            extraccion_diario
        ]
    }
)

# --- 3. EJECUCIÓN DE LA NAVEGACIÓN ---
navegacion_sihm.run()
