import os
import json
import io
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st

# --- CONFIGURACIÓN DE LA PÁGINA STREAMLIT ---
st.set_page_config(
    page_title="Extracción de Datos ICC",
    page_icon="📥",
    layout="wide" # Configuración optimizada para visualización de tablas anchas
)

st.title("📥 Extractor de Datos Diarios - Plataforma ICC")
st.markdown("Esta herramienta realiza la autenticación automática en el portal REDMET para procesar el balance diario.")

# --- CONFIGURACIÓN DE CREDENCIALES OFICIALES ---
URL_LOGIN = "https://redmet.icc.org.gt/login"
URL_DATA_API = "https://redmet.icc.org.gt/redmet/comparativas"

USUARIO_WS = "webservice.insivumeh@icc.org.gt"
CONTRASENA_WS = "WebService"

# --- CÁLCULO DINÁMICO DE FECHAS ---
ahora = datetime.now()
fecha_ayer = ahora - timedelta(days=1)

FECHA_INICIO = fecha_ayer.strftime("%d/%m/%Y") + " 07:00"
FECHA_FIN = ahora.strftime("%d/%m/%Y") + " 07:00"

st.info(f"📅 **Rango de consulta automático:** Desde {FECHA_INICIO} hasta {FECHA_FIN}")

# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN ---
if "df_procesado" not in st.session_state:
    st.session_state.df_procesado = None
if "nombre_archivo" not in st.session_state:
    st.session_state.nombre_archivo = ""

# --- FUNCIÓN NATIVA DE EXTRACCIÓN ---
def ejecutar_extraccion():
    IDS_ESTACIONES = "3,37,33,14,1,17,25,31,21,15,24,22,5,6,11,13,29,30,4,20,26,23,9,10,34,28,8,19,27,"
    VARIABLES_SQL = "AVG(temperatura) AS temperatura,MIN(temperatura) AS temperatura_minima,MAX(temperatura) AS temperatura_maxima,SUM(precipitacion) AS precipitacion,"
    RAW_VARIABLES = "temperatura,precipitacion,"

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
        
        # PASO 4: Descarga y conversión a DataFrame
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
                    df = pd.read_excel(contenido_binario, skiprows=4)
                    
                    if not df.empty:
                        df.columns = [str(col).strip() for col in df.columns]
                        mapeo_columnas = {
                            'Estacion': 'Estacion', 'Fecha': 'Fecha',
                            'temperatura': 'temperatura', 'temperatura minima': 'temperatura minima',
                            'temperatura maxima': 'temperatura maxima', 'precipitacion': 'precipitacion'
                        }
                        df = df.rename(columns=mapeo_columnas)
                        columnas_validas = ["Estacion", "Fecha", "temperatura", "temperatura minima", "temperatura maxima", "precipitacion"]
                        df = df[[col for col in columnas_validas if col in df.columns]]
                        
                        if 'Fecha' in df.columns:
                            df['Fecha'] = df['Fecha'].astype(str).str.split().str[0]
                        
                        df = df.sort_values(by=["Estacion", "Fecha"]).reset_index(drop=True)
                        return df
    except Exception as e:
        st.error(f"❌ Error durante el ciclo de extracción: {e}")
    return None

# --- INTERFAZ DE USUARIO: BOTONES EN COLUMNAS ---
col1, col2 = st.columns(2)

with col1:
    if st.button("🚀 Extraer Datos de Servidor", use_container_width=True):
        with st.spinner("Conectando con REDMET ICC y procesando matrices..."):
            df_resultado = ejecutar_extraccion()
            if df_resultado is not None and not df_resultado.empty:
                st.session_state.df_procesado = df_resultado
                st.session_state.nombre_archivo = f"reporte_dato_diario_ICC_{ahora.strftime('%Y%m%d_%H%M')}.csv"
                st.success(f"¡Extracción completada! Se consolidaron {len(df_resultado)} registros.")
            else:
                st.error("No se pudieron recuperar datos. Verifica la disponibilidad del servidor del ICC.")

with col2:
    if st.session_state.df_procesado is not None:
        # Convertimos el DataFrame en memoria a formato CSV decodificado para la descarga
        csv_buffer = io.StringIO()
        st.session_state.df_procesado.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        csv_data = csv_buffer.getvalue()

        st.download_button(
            label="💾 Descargar Archivo CSV",
            data=csv_data,
            file_name=st.session_state.nombre_archivo,
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.button("💾 Descargar Archivo CSV (Inactivo)", disabled=True, use_container_width=True)

# --- DESPLIEGUE DE LA VISTA PREVIA ---
if st.session_state.df_procesado is not None:
    st.markdown("---")
    st.subheader("📊 Vista Previa de la Matriz de Datos Extraída")
    st.dataframe(st.session_state.df_procesado, use_container_width=True)