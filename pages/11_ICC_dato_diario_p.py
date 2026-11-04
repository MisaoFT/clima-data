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
    page_title="Extracción y Matriz ICC",
    page_icon="📥",
    layout="wide"
)

st.title("📥 Extractor de Datos Diarios y Matriz Consolidada - REDMET ICC")
st.markdown("Herramienta de autenticación, extracción de balance diario, construcción de matriz de balance meteorológico y control de calidad.")

# --- CONFIGURACIÓN DE CREDENCIALES Y PARÁMETROS OFICIALES ---
URL_LOGIN = "https://redmet.icc.org.gt/login"
URL_DATA_API = "https://redmet.icc.org.gt/redmet/comparativas"

USUARIO_WS = st.secrets["CLIMAUSER"]
CONTRASENA_WS = st.secrets["CLIMACON"]

# Lista Maestra de Estaciones (Plantilla Oficial ICC)
ESTACIONES_MAESTRAS = [
    'Alamo', 'Amazonas', 'Bonanza', 'Bouganvilia', 'Cengicaña', 'Chiquirines', 
    'Cocales', 'Concepción', 'Costa Brava', 'El Bálsamo', 'El Platanar', 'Irlanda', 
    'La Candelaria', 'La Giralda', 'La Maquina', 'Lorena', 'Naranjales', 'Petén Oficina', 
    'Providencia', 'Puyumate', 'San Antonio EV', 'San Nicolás', 'San Rafael', 
    'Tehuantepeq', 'Trinidad', 'Trinidad Magdalena', 'Tululá', 'Xoluta', 'Yepocapa (FCA-CATIE)'
]

# --- CÁLCULO DINÁMICO DE FECHAS ---
ahora = datetime.now()
fecha_ayer = ahora - timedelta(days=1)

FECHA_INICIO = fecha_ayer.strftime("%d/%m/%Y") + " 07:00"
FECHA_FIN = ahora.strftime("%d/%m/%Y") + " 07:00"

st.info(f"📅 **Rango de consulta automático:** Desde {FECHA_INICIO} hasta {FECHA_FIN}")

# --- INICIALIZACIÓN DEL ESTADO DE SESIÓN ---
if "df_procesado" not in st.session_state:
    st.session_state.df_procesado = None
if "df_matriz" not in st.session_state:
    st.session_state.df_matriz = None
if "reporte_qc" not in st.session_state:
    st.session_state.reporte_qc = []

# --- FUNCIÓN DE EXTRACCIÓN DE DATOS ---
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

        # PASO 3: Generación del reporte
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
                        columnas_validas = ["Estacion", "Fecha", "temperatura", "temperatura minima", "temperatura maxima", "precipitacion"]
                        df = df[[col for col in columnas_validas if col in df.columns]]
                        
                        if 'Fecha' in df.columns:
                            df['Fecha'] = df['Fecha'].astype(str).str.split().str[0]
                        
                        # Limpiar filas de resumen extra de la API si existieran
                        df = df[df['Fecha'].str.match(r'^\d{4}-\d{2}-\d{2}$', na=False)]
                        df = df.sort_values(by=["Estacion", "Fecha"]).reset_index(drop=True)
                        return df
    except Exception as e:
        st.error(f"❌ Error durante el ciclo de extracción: {e}")
    return None

# --- FUNCIÓN DE CONSTRUCCIÓN DE MATRIZ Y CONTROL DE CALIDAD ---
def procesar_matriz_y_qc(df_raw):
    fechas = sorted(df_raw['Fecha'].unique())
    if len(fechas) < 2:
        st.warning("⚠️ No se encontraron 2 días completos de datos para construir la matriz.")
        return None, []

    dia_1, dia_2 = fechas[0], fechas[1]
    
    columnas_matriz = ['FECHA', 'VARIABLE'] + ESTACIONES_MAESTRAS
    matriz_rows = [
        {'FECHA': dia_1, 'VARIABLE': 'LLUVIA'},
        {'FECHA': dia_1, 'VARIABLE': 'TMAX'},
        {'FECHA': dia_1, 'VARIABLE': 'TMED'},
        {'FECHA': dia_2, 'VARIABLE': 'TMIN'}
    ]

    reporte_qc = []

    for estacion in ESTACIONES_MAESTRAS:
        df_est = df_raw[df_raw['Estacion'] == estacion]
        
        if df_est.empty:
            matriz_rows[0][estacion] = 'NA'
            matriz_rows[1][estacion] = 'NA'
            matriz_rows[2][estacion] = 'NA'
            matriz_rows[3][estacion] = 'NA'
            reporte_qc.append(f"ℹ️ **Estación no reportada**: La estación `{estacion}` no retornó información de servidor (NA asignado).")
            continue

        df_d1 = df_est[df_est['Fecha'] == dia_1]
        df_d2 = df_est[df_est['Fecha'] == dia_2]

        # 1. Sumatoria de Lluvia de 2 Días
        val_lluvia = df_est['precipitacion'].sum(min_count=1)
        if pd.isna(val_lluvia):
            matriz_rows[0][estacion] = 'NA'
        else:
            val_lluvia = round(float(val_lluvia), 1)
            matriz_rows[0][estacion] = val_lluvia
            # QC 6 y 7
            if val_lluvia > 200.0:
                reporte_qc.append(f"🚨 **ALERTA CRÍTICA DE LLUVIA**: `{estacion}` registró **{val_lluvia} mm** acumulados en 2 días (> 200 mm).")
            elif val_lluvia > 30.0:
                reporte_qc.append(f"⚠️ **Revisión de Lluvia Alta**: `{estacion}` acumuló **{val_lluvia} mm** en 2 días (> 30 mm).")

        # 2. Tmax del Día 1
        if not df_d1.empty and not pd.isna(df_d1['temperatura maxima'].values[0]):
            val_tmax = round(float(df_d1['temperatura maxima'].values[0]), 1)
            matriz_rows[1][estacion] = val_tmax
            # QC 8
            if val_tmax >= 38.0:
                reporte_qc.append(f"⚠️ **Revisión Tmax fuera de límite**: `{estacion}` registró Tmax Día 1 de **{val_tmax} °C** (Debe ser < 38 °C).")
        else:
            matriz_rows[1][estacion] = 'NA'

        # 3. Tmed del Día 1
        if not df_d1.empty and not pd.isna(df_d1['temperatura'].values[0]):
            val_tmed = round(float(df_d1['temperatura'].values[0]), 1)
            matriz_rows[2][estacion] = val_tmed
        else:
            matriz_rows[2][estacion] = 'NA'

        # 4. Tmin del Día 2
        if not df_d2.empty and not pd.isna(df_d2['temperatura minima'].values[0]):
            val_tmin = round(float(df_d2['temperatura minima'].values[0]), 1)
            matriz_rows[3][estacion] = val_tmin
            # QC 9
            if val_tmin <= 10.0:
                reporte_qc.append(f"⚠️ **Revisión Tmin fuera de límite**: `{estacion}` registró Tmin Día 2 de **{val_tmin} °C** (Debe ser > 10 °C).")
        else:
            matriz_rows[3][estacion] = 'NA'

    df_matriz_final = pd.DataFrame(matriz_rows)[columnas_matriz]
    return df_matriz_final, reporte_qc


# --- INTERFAZ DE USUARIO Y PROCESAMIENTO ---
if st.button("🚀 Extraer Datos y Generar Matriz Consolidada", use_container_width=True):
    with st.spinner("Conectando con REDMET ICC, extrayendo variables y calculando matriz..."):
        df_resultado = ejecutar_extraccion()
        if df_resultado is not None and not df_resultado.empty:
            st.session_state.df_procesado = df_resultado
            df_matriz_out, qc_out = procesar_matriz_y_qc(df_resultado)
            st.session_state.df_matriz = df_matriz_out
            st.session_state.reporte_qc = qc_out
            st.success("¡Proceso completado con éxito!")
        else:
            st.error("No se pudieron recuperar datos. Verifica la disponibilidad del servidor del ICC.")

# --- DESPLIEGUE DE RESULTADOS Y DESCARGAS ---
if st.session_state.df_matriz is not None:
    st.markdown("---")
    st.subheader("🛡️ Reporte de Control de Calidad y Alertas")
    
    if st.session_state.reporte_qc:
        for obs in st.session_state.reporte_qc:
            st.markdown(obs)
    else:
        st.success("✅ Todas las estaciones se encuentran dentro de los rangos normales de temperatura y precipitación.")

    st.markdown("---")
    st.subheader("📊 Matriz Meteorológica Consolidada")
    st.dataframe(st.session_state.df_matriz, use_container_width=True)

    # Preparación de descargas
    col_dl1, col_dl2, col_dl3 = st.columns(3)
    
    # 1. Matriz Excel
    output_excel = io.BytesIO()
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        st.session_state.df_matriz.to_excel(writer, index=False, sheet_name='Matriz_ICC')
    data_excel = output_excel.getvalue()

    # 2. Matriz CSV
    csv_matriz_buffer = io.StringIO()
    st.session_state.df_matriz.to_csv(csv_matriz_buffer, index=False, encoding='utf-8-sig')
    
    # 3. CSV Datos Crudos
    csv_raw_buffer = io.StringIO()
    st.session_state.df_procesado.to_csv(csv_raw_buffer, index=False, encoding='utf-8-sig')

    stamp_time = ahora.strftime('%Y%m%d_%H%M')
    
    with col_dl1:
        st.download_button(
            label="💾 Descargar Matriz (Excel .xlsx)",
            data=data_excel,
            file_name=f"matriz_balance_ICC_{stamp_time}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with col_dl2:
        st.download_button(
            label="📄 Descargar Matriz (CSV)",
            data=csv_matriz_buffer.getvalue(),
            file_name=f"matriz_balance_ICC_{stamp_time}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col_dl3:
        st.download_button(
            label="📋 Descargar Datos Crudos (CSV)",
            data=csv_raw_buffer.getvalue(),
            file_name=f"reporte_dato_diario_ICC_{stamp_time}.csv",
            mime="text/csv",
            use_container_width=True
        )
