import io
import unicodedata
import numpy as np
import pandas as pd
import streamlit as st

# ==========================================
# CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Generador de Matriz Meteorológica INSIVUMEH",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Generador de Matriz Diaria Meteorológica (INSIVUMEH)")
st.markdown(
    "Sube tu archivo `consolidado_kobo_valido.xlsx` para transformarlo "
    "en la matriz final pivotada `dato_diario_preliminar` con las 64 estaciones oficiales."
)

# Estructura oficial de 64 estaciones Insivumeh
ESTACIONES_ESTRUCTURA = {
    "CAMOTAN": "INS200501CV", "CATARINA": "INS121601CV", "CHAMPERICO FEGUA": "INS110701CV",
    "COBAN": "INS160101CV", "EL CAPITAN": "INS071301CV", "ESQUIPULAS": "INS200701CV",
    "FLORES AEROPUERTO": "INS170101CV", "LA AURORA": "INS010102CV", "LA CEIBITA": "INS210601CV",
    "LA FRAGUA": "INS190201CV", "LABOR OVALLE": "INS090301CV", "LOS ALTOS": "INS090101CV",
    "MAZATENANGO": "INS100101CV", "MONTUFAR": "INS221401CV", "PANZÓS PHC ALTAVERAPAZ": "INS160701CV",
    "PUERTO BARRIOS PHC": "INS180101CV", "RETALHULEU AEROPUERTO": "INS110101CV", "SACAPULAS": "INS141601CV",
    "SAN MARCOS PHC": "INS120101CV", "SANTA CRUZ BALANYÁ": "INS041001CV", "TODOS SANTOS": "INS131501CV",
    "INSIVUMEH": "INS010101CV", "ALAMEDA ICTA": "INS040101CV", "ASUNCION MITA": "INS220501CV",
    "CHINIQUE": "INS140301CV", "EL TABLON": "INS070101CV", "HUEHUETENANGO": "INS130101CV",
    "LA UNION": "INS190901CV", "LAS VEGAS PHC": "INS180201CV", "NEBAJ": "INS141301CV",
    "POPTUN": "INS171201CV", "QUEZADA": "INS221701CV", "SABANA GRANDE": "INS050101CV",
    "SAN AGUSTIN ACASAGUASTLAN": "INS020302CV", "SAN JERONIMO": "INS150701CV", "SAN JOSE AEROPUERTO": "INS050901CV",
    "SAN PEDRO NECTA": "INS130601CV", "SANTA MARIA CAHABON": "INS161201CV", "SANTIAGO ATITLAN": "INS071901CV",
    "SUIZA CONTENTA": "INS030801CV", "TECUN UMAN": "INS121701CV", "CHIXOY PCH": "INS141901CV",
    "CUBULCO": "INS150301CV", "LOS ALBORES": "INS150101CV", "LOS ESCLAVOS": "INS060201CV",
    "PASABIEN": "INS190301CV", "POTRERO CARRILLO": "INS020501CV", "SAN MARTIN JILOTEPEQUE": "INS040501CV",
    "AMATITLAN": "INS011401AT", "ANTIGUA GUATEMALA": "INS030101CV", "CONCEPCION": "INS120701CV",
    "IXCHIGUAN": "INS121001CV", "JALAPA": "INS210101CV", "LA REFORMA": "INS121301CV",
    "LO DE COY": "INS010701CV", "MARISCOS": "INS180501AT", "MORALES MET": "INS180401AT",
    "PACHUTÉ": "INS040701CV", "PLAYA GRANDE IXCAN": "INS142101CV", "SAN JOSE PINULA": "INS011001CV",
    "SAN PEDRO AYAMPUC": "INS010401CV", "SANTA CRUZ DEL QUICHE": "INS140101CV", "SANTA MARGARITA": "INS190501CV",
    "TOTONICAPAN": "INS080101CV"
}

VARIABLES_ORDENADAS = [
    "LLUVIA", "TMAX", "TMIN", "TMED", "BRILLO SOLAR", "RADIACION",
    "EVA_TANQUE", "EVA_PICHE", "NUBOSIDAD", "DIR_VIENTO", "VEL_VIENTO",
    "HUMEDAD_REL", "PRESION_ATM", "TSUELO100"
]

MAPEO_VARIABLES = {
    "LLUVIA_ACUM": "LLUVIA",
    "TMAX": "TMAX",
    "TMIN": "TMIN",
    "TMED": "TMED",
    "BRILLO_SOLAR_18H": "BRILLO SOLAR",
    "RADIACION_SOLAR": "RADIACION",
    "EVAPORACION_TANQUE_07H": "EVA_TANQUE",
    "EVAPORACION_PICHE_07H": "EVA_PICHE",
    "Nubosidad_Diaria_Cod": "NUBOSIDAD",
    "Dir_Viento_Diaria_Deg": "DIR_VIENTO",
    "Humedad_Diaria_Pct": "HUMEDAD_REL",
    "Presion_Diaria_hPa": "PRESION_ATM",
    "TSUELO_100CM": "TSUELO100"
}


def normalizar_texto(texto):
    if not isinstance(texto, str):
        return ""
    texto = texto.upper().strip()
    texto = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return texto.replace("_", " ").replace("-", " ")


def transformar_consolidado_a_matriz(df_consolidado: pd.DataFrame) -> pd.DataFrame:
    """Transforma la tabla de consolidado plano a la matriz final de 64 estaciones por fecha/variable."""
    df_consolidado["Fecha_dt"] = pd.to_datetime(df_consolidado["Fecha"], errors="coerce")

    dict_norm = {normalizar_texto(k): k for k in ESTACIONES_ESTRUCTURA.keys()}
    dict_norm["AMATITLAN 2"] = "AMATITLAN"
    dict_norm["CHINIQUE.1"] = "CHINIQUE"
    dict_norm["PACHUTE"] = "PACHUTÉ"

    registros_largos = []

    for _, row in df_consolidado.iterrows():
        est_raw = normalizar_texto(row["Estacion"])
        est_oficial = dict_norm.get(est_raw, None)

        if est_oficial is None:
            for k_norm, k_orig in dict_norm.items():
                if est_raw in k_norm or k_norm in est_raw:
                    est_oficial = k_orig
                    break

        if est_oficial is None or pd.isnull(row["Fecha_dt"]):
            continue

        fecha_obs = row["Fecha_dt"]

        for col_orig, var_drive in MAPEO_VARIABLES.items():
            if col_orig in row and pd.notnull(row[col_orig]):
                val = row[col_orig]
                # Desplazamiento climatológico oficial: -1 día para lluvia observada a las 07:00 h
                if var_drive == "LLUVIA":
                    fecha_aplicada = fecha_obs - pd.Timedelta(days=1)
                else:
                    fecha_aplicada = fecha_obs

                registros_largos.append({
                    "fecha_dt": fecha_aplicada,
                    "fecha_str": fecha_aplicada.strftime("%d/%m/%Y"),
                    "variable": var_drive,
                    "estacion": est_oficial,
                    "valor": val
                })

    df_largo = pd.DataFrame(registros_largos)

    if df_largo.empty:
        return pd.DataFrame(columns=["fecha", "variable"] + list(ESTACIONES_ESTRUCTURA.keys()))

    matriz_pivot = df_largo.pivot_table(
        index=["fecha_dt", "fecha_str", "variable"],
        columns="estacion",
        values="valor",
        aggfunc="first"
    ).reset_index()

    matriz_pivot["var_order"] = matriz_pivot["variable"].apply(
        lambda x: VARIABLES_ORDENADAS.index(x) if x in VARIABLES_ORDENADAS else 99
    )
    matriz_pivot = matriz_pivot.sort_values(by=["fecha_dt", "var_order"]).drop(columns=["fecha_dt", "var_order"])
    matriz_pivot = matriz_pivot.rename(columns={"fecha_str": "fecha"})

    for est in ESTACIONES_ESTRUCTURA.keys():
        if est not in matriz_pivot.columns:
            matriz_pivot[est] = np.nan

    cols_finales = ["fecha", "variable"] + list(ESTACIONES_ESTRUCTURA.keys())
    return matriz_pivot.reindex(columns=cols_finales)


# ==========================================
# CARGA DE ARCHIVO ÚNICA
# ==========================================
st.sidebar.header("📁 Archivo de Entrada")
file_excel = st.sidebar.file_uploader(
    "Sube tu archivo Excel `consolidado_kobo_valido.xlsx`",
    type=["xlsx", "xls"]
)

if file_excel:
    with st.spinner("Leyendo archivo consolidado..."):
        df_cons = pd.read_excel(file_excel)
        st.success("¡Archivo cargado correctamente!")
        st.info(f"Registros encontrados: **{len(df_cons)}** filas.")

        if st.button("🚀 Generar Matriz Pivotada"):
            with st.spinner("Generando matriz de 64 estaciones y aplicando reglas climatológicas..."):
                matriz_final = transformar_consolidado_a_matriz(df_cons)

                st.success("✅ ¡Matriz `dato_diario_preliminar` generada exitosamente!")
                st.subheader("📋 Vista Previa de la Matriz Generada")
                st.dataframe(matriz_final.head(15), use_container_width=True)

                # Preparar descargas
                csv_bytes = matriz_final.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

                output_excel = io.BytesIO()
                with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
                    matriz_final.to_excel(writer, index=False, sheet_name="Matriz_Drive")
                excel_bytes = output_excel.getvalue()

                st.markdown("---")
                st.subheader("📥 DESCARGAS DISPONIBLES")
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.download_button(
                        label="📄 Descargar dato_diario_preliminar.csv",
                        data=csv_bytes,
                        file_name="dato_diario_preliminar.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                with col_d2:
                    st.download_button(
                        label="📊 Descargar dato_diario_preliminar.xlsx",
                        data=excel_bytes,
                        file_name="dato_diario_preliminar.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
else:
    st.info("👈 Por favor, sube tu archivo `consolidado_kobo_valido.xlsx` en el panel lateral para continuar.")
