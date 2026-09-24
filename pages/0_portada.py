import streamlit as st

# --- CONTENIDO VISUAL DE LA PORTADA PRINCIPAL ---
st.title("🌍 Sistema Integrado de Herramientas Meteorológicas (SIHM)")
st.markdown("---")

st.markdown("""
### ¡Bienvenida al Centro de Control Meteorológico!
Utiliza el nuevo menú lateral izquierdo para acceder a las herramientas organizadas por categorías de procesamiento.
""")

st.info("💡 **Nota de uso:** Los módulos estacionales de lluvias parciales operan óptimamente durante el ciclo de monitoreo activo.")

st.markdown("---")
st.subheader("🛠️ Módulos de Operación Disponibles:")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    #### 🌧️ Datos Parciales de Lluvia
    * **Procesador Kobo:** Normalización, orden cronológico e inyección matricial con formato `NA`.
    * **Procesador ICC (Parcial):** Estructuración de matrices de lluvia estacional.
    * **Visualizador:** Generación cartográfica de capas de precipitación.
    """)

with col2:
    st.markdown("""
    #### 📥 Datos Diarios
    * **Extractor REDMET:** Automatización y descarga directa de flujos binarios desde el web service oficial del ICC.
    """)