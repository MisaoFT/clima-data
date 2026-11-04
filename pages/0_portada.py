import streamlit as st

# --- TÍTULO Y PRESENTACIÓN ---
st.markdown(
    """
    <h1 style='text-align: center; margin-bottom: 20px;'>
        🌍 Sección de Climatología<br>
        <span style='font-size: 0.85em; font-weight: normal;'>Sistema Integrado de Herramientas Meteorológicas (SIHM)</span>
    </h1>
    """, 
    unsafe_allow_html=True
)

st.subheader("¡Bienvenida al centro de control de Datos Diarios Preliminares!")
st.markdown("Utiliza el nuevo menú lateral izquierdo para acceder a las herramientas organizadas por categorías de procesamiento.")

st.info("💡 **Nota de uso:** Los módulos estacionales de lluvias parciales operan óptimamente durante el ciclo de monitoreo activo.")

st.divider()

# --- SECCIÓN DE MÓDULOS DE OPERACIÓN ---
st.subheader("🛠️ Módulos de operación disponibles:")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📊 Datos Diarios Preliminares")
    
    st.markdown("""
    * **1. Extractor REDMET - ICC:**
      Automatización de extracción y descarga directa de flujos meteorológicos de la red de estaciones del Instituto de Cambio Climático (ICC) para la generación de reportes unificados.
      
    * **2. Procesador KoboCollect:**
      Ingesta, limpieza y normalización de registros de campo descargados desde la plataforma KoboToolbox (estaciones climáticas, sinópticas y automáticas).
      
    * **3. Generador de matrices y documentos:**
      Estructuración matricial, control de calidad básico, unificación de variables meteorológicas y exportación formal para auditorías de datos diarios INSIVUMEH.
    """)

with col2:
    st.markdown("### 🌧️ Lluvias Parciales")
    
    st.markdown("""
    * **4. Extracción y procesamiento parcial:**
      Extracción de series temporales de precipitación acumulada parcial, filtrado de eventos extremos, ordenamiento cronológico e inyección matricial con formato estándar `NA`.
      
    * **Visualización cartográfica & análisis:**
      Generación y validación de mapas de precipitación, trazado de isoyetas y preparación de capas espaciales para el análisis estacional activo.
    """)

st.divider()

# --- CRÉDITOS Y PIE DE PÁGINA ---
st.caption("⚡ **SIHM Climatología** — Plataforma optimizada para la automatización, validación física y homogeneización de series de tiempo meteorológicas.")

# Mención de autoría visible
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888888; font-size: 0.9em;'>"
    "Desarrollado y diseñado por <b>Edwin García Plato</b> | Sección de Climatología"
    "</div>", 
    unsafe_allow_html=True
)
