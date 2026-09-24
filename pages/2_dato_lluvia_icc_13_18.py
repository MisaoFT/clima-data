import os
import json
import io
from datetime import datetime, timedelta
# Importamos zoneinfo para manejar zonas horarias geográficas de forma nativa
from zoneinfo import ZoneInfo 
import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st

# --- CONFIGURACIÓN DE LA PÁGINA STREAMLIT ---
st.set_page_config(
    page_title="Extracción ICC 13:00 a 18:00",
    page_icon="📥",
    layout="wide"
)

st.title("📥 Extracción REDMET-ICC lluvias parciales (13:00 a 18:00)")
st.markdown("Módulo estacional para la captura y consolidación de la precipitación acumulada durante la tarde.")

# --- CONFIGURACIÓN DE CREDENCIALES OFICIALES ---
URL_LOGIN = "https://redmet.icc.org.gt/login"
URL_DATA_API = "https://redmet.icc.org.gt/redmet/comparativas"

USUARIO_WS = st.secrets["ICC_USUARIO"]
CONTRASENA_WS = st.secrets["ICC_PASS"]

# --- CORRECCIÓN DE ZONA HORARIA EN EL SERVIDOR (HORA DE GUATEMALA UTC-6) ---
tz_guatemala = ZoneInfo("America/Guatemala")
ahora_gt = datetime.now(tz_guatemala)
fecha_hoy_gt = ahora_gt.strftime("%d/%m/%Y")

# Construimos los rangos basándonos estrictamente en el calendario de Guatemala
FECHA_INICIO = f"{fecha_hoy_gt} 13:00"
FECHA_FIN = f"{fecha_hoy_gt} 18:00"

st.info(f"📅 **Rango de consulta vespertino:** Desde {FECHA_INICIO} hasta {FECHA_FIN} (Hora de Guatemala)")

# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN INDEPENDIENTE ---
if "df_lluvia_13_18" not in st.session_state:
    st.session_state.df_lluvia_13_18 = None
if "nom_archivo_13_18" not in st.session_state:
    st.session_state.nom_archivo_13_18 = ""

# --- FUNCIÓN NATIVA DE EXTRACCIÓN ---
def ejecutar_extraccion_vespertina():
    IDS_ESTACIONES = "3,37,33,14,1,17,25,31,21,15,24,22,5,6,11,13,29,30,4,20,26,23,9,10,34,28,8,19,27,"
    VARIABLES_SQL = "SUM(precipitacion) AS precipitacion,"
    RAW_VARIABLES = "precipitacion,"

    session = requests.Session()
    headers_base = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "es-ES,es;q=0.9",
        "Origin": "https://redmet.icc.org.gt",
        "Referer": "https://redmet.icc.org.gt/redmet/comparativas",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        # PASO 1: Captura del Token CSRF
        get_login_page = session.get(URL_LOGIN, headers={"User-Agent": headers_base["User-Agent"]})
        soup = BeautifulSoup(get_login_page.text, 'html.parser')
        
        csrf_token = None
        input_token = soup.find('input', {'name': '_token'}) or soup.find('meta', {'name': 'csrf-token'})
        if input_token:
            csrf_token = input_token.get('value') or input_token.get('content')

        # PASO 2: Autenticación de Sesión
        payload_auth = {"email": USUARIO_WS, "password": CONTRASENA_WS}
        if csrf_token:
            payload_auth["_token"] = csrf_token

        headers_login = headers_base.copy()
        headers_login["Content-Type"] = "application/x-www-form-urlencoded"
        session.post(URL_LOGIN, data=payload_auth, headers=headers_login)

        # PASO 3: Ordenar la generación en el servidor
        payload_query = {
            "type": "excel",  
            "txFechaIni": FECHA_INICIO,
            "txFechaFin": FECHA_FIN,
            "agrupar": "Dia",
            "estaciones": IDS_ESTACIONES,
            "variables": VARIABLES_SQL,
            "raw": RAW_VARIABLES
        }

        headers_reporte = headers_base.copy()
        headers_reporte["Content-Type"] = "application/x-www-form-urlencoded"
        if csrf_token:
            headers_reporte["X-CSRF-TOKEN"] = csrf_token

        response_datos = session.post(URL_DATA_API, data=payload_query, headers=headers_reporte)
        
        # PASO 4: Descarga binaria y conversión a DataFrame usando el motor Openpyxl
        if response_datos.status_code == 200:
            respuesta_json = response_datos.json()
            nombre_archivo_temp = respuesta_json.get("filename")

            if nombre_archivo_temp:
                url_descarga_real = f"https://redmet.icc.org.gt/tmpxls/{nombre_archivo_temp}"
                headers_descarga = headers_base.copy()
                headers_descarga["Accept"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/octet-stream"
                
                response_file = session.get(url_descarga_real, headers=headers_descarga)
                
                if response_file.status_code == 200:
                    contenido_binario = io.BytesIO(response_file.content)
                    df = pd.read_excel(contenido_binario, skiprows=4, engine='openpyxl')
                    
                    if not df.empty:
                        df.columns = [str(col).strip() for col in df.columns]
                        
                        mapeo_columnas = {
                            'Estacion': 'Estacion', 'Fecha': 'Fecha',
                            'precipitacion': 'precipitacion'
                        }
                        df = df.rename(columns=mapeo_columnas)
                        columnas_validas = ["Estacion", "Fecha", "precipitacion"]
                        df = df[[col for col in columnas_validas if col in df.columns]]
                        
                        if 'Fecha' in df.columns:
                            df['Fecha'] = df['Fecha'].astype(str).str.split().str[0]
                        
                        df = df.sort_values(by=["Estacion", "Fecha"]).reset_index(drop=True)
                        return df
    except Exception as e:
        st.error(f"❌ Error durante el ciclo de procesamiento: {e}")
    return None

# --- INTERFAZ WEB: CONTROL DE ACCIONES ---
col1, col2 = st.columns(2)

with col1:
    if st.button("🚀 Extraer precipitación de estaciones de ICC", use_container_width=True):
        with st.spinner("Conectando con REDMET y calculando acumulados parciales..."):
            df_resultado = ejecutar_extraccion_vespertina()
            if df_resultado is not None and not df_resultado.empty:
                st.session_state.df_lluvia_13_18 = df_resultado
                st.session_state.nom_archivo_13_18 = f"Lluvias_parciales_13_18_horas_{ahora_gt.strftime('%Y%m%d_%H%M')}.csv"
                st.success(f"¡Extracción Exitosa! Se consolidaron {len(df_resultado)} estaciones.")
            else:
                st.error("No se encontraron registros de lluvia para este rango de horas o el servidor no respondió.")

with col2:
    if st.session_state.df_lluvia_13_18 is not None:
        csv_buffer = io.StringIO()
        # Redondeamos a 1 decimal en el archivo CSV de salida para mantener concordancia
        df_csv = st.session_state.df_lluvia_13_18.copy()
        if 'precipitacion' in df_csv.columns:
            df_csv['precipitacion'] = df_csv['precipitacion'].round(1)
            
        df_csv.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        csv_data = csv_buffer.getvalue()

        st.download_button(
            label="💾 Descargar .csv de precipitación ",
            data=csv_data,
            file_name=st.session_state.nom_archivo_13_18,
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.button("💾 Descargar .csv de precipitación (Inactivo)", disabled=True, use_container_width=True)

# --- PANEL METEOROLÓGICO Y TABLA DE VERIFICACIÓN ---
if st.session_state.df_lluvia_13_18 is not None:
    st.markdown("---")
    
    # Bloque de métricas globales ajustado a un decimal (.1f)
    if 'precipitacion' in st.session_state.df_lluvia_13_18.columns:
        total_mm = st.session_state.df_lluvia_13_18['precipitacion'].sum()
        
        metric_col1, metric_col2 = st.columns(2)
        with metric_col1:
            st.metric(label="🌧️ Precipitación total acumulada (Tarde)", value=f"{total_mm:.1f} mm")
        with metric_col2:
            promedio_mm = st.session_state.df_lluvia_13_18['precipitacion'].mean()
            st.metric(label="📊 Promedio por estación (tarde)", value=f"{promedio_mm:.1f} mm")

    st.markdown("---")
    
    # --- SECCIÓN: TOP 10 ESTACIONES CON MÁS LLUVIA (TARDE) ---
    st.subheader("🏆 Top 10 Estaciones con mayor precipitación (Vespertino)")
    
    top_10_vespertino_df = (
        st.session_state.df_lluvia_13_18
        .sort_values(by="precipitacion", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )
    
    top_10_vespertino_df.index = top_10_vespertino_df.index + 1
    
    # Mostramos la tabla formateando numéricamente la columna a un único decimal flotante
    st.dataframe(
        top_10_vespertino_df.style
        .background_gradient(cmap="Blues", subset=["precipitacion"])
        .format({"precipitacion": "{:.1f}"}), 
        use_container_width=True
    )
    
    st.markdown("---")

    # --- TABLA COMPLETA ORIGINAL ---
    st.subheader("📊 Matriz completa de lluvia procesada (13:00 a 18:00)")
    # También forzamos visualmente 1 decimal en la matriz completa
    st.dataframe(
        st.session_state.df_lluvia_13_18.style.format({"precipitacion": "{:.1f}"}), 
        use_container_width=True
    )
