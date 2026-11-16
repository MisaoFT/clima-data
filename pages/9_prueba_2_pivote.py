import io
import unicodedata
import numpy as np
import pandas as pd
import streamlit as st

# ==========================================
# CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Generación de documento de dato diario preliminar INSIVUMEH",
    page_icon="🧾",
    layout="wide",
)

st.title("📊 Documento de dato diario preliminar (documento_drive)")
st.markdown(
    "Sube tu archivo consolidado (`consolidado_kobo_valido.xlsx`) "
    "para transformarlo en la matriz oficial `dato_diario_preliminar` con las 67 estaciones."
)

# ==========================================
# PANEL LATERAL: ARCHIVO DE ENTRADA
# ==========================================
st.sidebar.header("📁 Archivo de entrada")
file_excel = st.sidebar.file_uploader(
    "Sube tu archivo Excel consolidado",
    type=["xlsx", "xls"]
)

# Estructura oficial de estaciones INSIVUMEH
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
    "IXCHIGUAN": "INS121001CV", "JALAPA": "INS210101CV", "LA REFORMA": "INS121301CV", "LAS NUBES": "INS010302AT",
    "LO DE COY": "INS010701CV", "MARISCOS": "INS180501AT", "MORALES MET": "INS180401AT", "NENTON": "INS130501AT", "NUEVA CONCEPCION": "INS090901AT",
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
    return " ".join(texto.replace("_", " ").replace("-", " ").split())


def parsear_fecha_consolidado(serie_fecha: pd.Series) -> pd.Series:
    """Parsea fechas tanto en formato YYYY-MM-DD como DD/MM/YYYY."""
    s = serie_fecha.astype(str).str.strip().str.split(" ").str[0]
    dt_iso = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    dt_lat = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    dt_mix = pd.to_datetime(s, dayfirst=True, errors="coerce")
    return dt_iso.fillna(dt_lat).fillna(dt_mix).dt.normalize()


def transformar_consolidado_a_matriz(df_consolidado: pd.DataFrame) -> pd.DataFrame:
    """Transforma el consolidado plano a la matriz oficial de 67 estaciones por fecha/variable."""
    df_consolidado = df_consolidado.copy()
    df_consolidado["Fecha_dt"] = parsear_fecha_consolidado(df_consolidado["Fecha"])

    dict_norm = {normalizar_texto(k): k for k in ESTACIONES_ESTRUCTURA.keys()}
    dict_norm["AMATITLAN 2"] = "AMATITLAN"
    dict_norm["CHINIQUE.1"] = "CHINIQUE"
    dict_norm["CHINIQUE 1"] = "CHINIQUE"
    dict_norm["PACHUTE"] = "PACHUTÉ"
    dict_norm["RETALHULEU AREOPUERTO"] = "RETALHULEU AEROPUERTO"
    dict_norm["PANZOS PHC"] = "PANZÓS PHC ALTAVERAPAZ"

    registros_largos = []
    fechas_con_datos = set()

    for _, row in df_consolidado.iterrows():
        est_raw = normalizar_texto(str(row.get("Estacion", "")))
        est_oficial = dict_norm.get(est_raw, None)

        if est_oficial is None and est_raw:
            for k_norm, k_orig in dict_norm.items():
                if est_raw in k_norm or k_norm in est_raw:
                    est_oficial = k_orig
                    break

        fecha_obs = row["Fecha_dt"]
        if est_oficial is None or pd.isnull(fecha_obs):
            continue

        for col_orig, var_drive in MAPEO_VARIABLES.items():
            if col_orig in row and pd.notnull(row[col_orig]):
                val = pd.to_numeric(row[col_orig], errors="coerce")
                if pd.isnull(val):
                    continue

                fechas_con_datos.add(fecha_obs)
                registros_largos.append({
                    "fecha_dt": fecha_obs,
                    "variable": var_drive,
                    "estacion": est_oficial,
                    "valor": val
                })

    if not registros_largos:
        return pd.DataFrame(columns=["fecha", "variable"] + list(ESTACIONES_ESTRUCTURA.keys()))

    df_largo = pd.DataFrame(registros_largos)

    # Agrupar posibles duplicados de estación/fecha/variable
    df_lluv = df_largo[df_largo["variable"] == "LLUVIA"].groupby(
        ["fecha_dt", "variable", "estacion"], as_index=False
    )["valor"].sum()

    df_otras = df_largo[df_largo["variable"] != "LLUVIA"].groupby(
        ["fecha_dt", "variable", "estacion"], as_index=False
    )["valor"].mean()

    df_largo_clean = pd.concat([df_lluv, df_otras], ignore_index=True)

    # Construir esqueleto solo para fechas que efectivamente tienen al menos 1 dato válido
    todas_fechas = sorted(list(fechas_con_datos))
    vars_activas = [v for v in VARIABLES_ORDENADAS if v in df_largo_clean["variable"].unique()]
    if "LLUVIA" not in vars_activas:
        vars_activas.insert(0, "LLUVIA")

    multi_idx = pd.MultiIndex.from_product(
        [todas_fechas, vars_activas],
        names=["fecha_dt", "variable"]
    )

    matriz_pivot = df_largo_clean.pivot(
        index=["fecha_dt", "variable"],
        columns="estacion",
        values="valor"
    ).reindex(multi_idx).reset_index()

    matriz_pivot["fecha"] = matriz_pivot["fecha_dt"].dt.strftime("%d/%m/%Y")
    matriz_pivot = matriz_pivot.drop(columns=["fecha_dt"])

    for est in ESTACIONES_ESTRUCTURA.keys():
        if est not in matriz_pivot.columns:
            matriz_pivot[est] = np.nan

    cols_finales = ["fecha", "variable"] + list(ESTACIONES_ESTRUCTURA.keys())
    return matriz_pivot.reindex(columns=cols_finales)


# ==========================================
# EJECUCIÓN EN INTERFAZ STREAMLIT
# ==========================================
if file_excel:
    with st.spinner("Leyendo archivo consolidado..."):
        df_cons = pd.read_excel(file_excel)
        st.success("¡Archivo cargado correctamente!")
        st.info(f"Registros encontrados en el consolidado: **{len(df_cons)}** filas.")

        if st.button("🚀 Generar documento diario"):
            with st.spinner("Generando matriz oficial..."):
                matriz_final = transformar_consolidado_a_matriz(df_cons)

                st.success("✅ ¡Matriz `dato_diario_preliminar` generada exitosamente!")

                # Auditoría detallada de lluvia por fecha
                with st.expander("🌧️ Cobertura de LLUVIA por fecha en la Matriz", expanded=True):
                    df_check_lluvia = matriz_final[matriz_final["variable"] == "LLUVIA"].copy()
                    est_cols = list(ESTACIONES_ESTRUCTURA.keys())
                    df_check_lluvia["Total_Estaciones_con_Lluvia"] = df_check_lluvia[est_cols].notnull().sum(axis=1)
                    df_check_lluvia["Estaciones_con_Lluvia_>0mm"] = (df_check_lluvia[est_cols] > 0).sum(axis=1)
                    st.dataframe(
                        df_check_lluvia[["fecha", "Total_Estaciones_con_Lluvia", "Estaciones_con_Lluvia_>0mm"]],
                        use_container_width=True
                    )
                    st.caption(
                        "💡 Nota: Si a partir de cierta fecha ves ~23 estaciones en lugar de ~50, "
                        "verifica que el CSV de Climáticas Convencionales descargado de Kobo incluya esos días."
                    )

                st.subheader("📋 Vista previa del documento")
                st.dataframe(matriz_final.head(28), use_container_width=True)

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
    st.info("👈 Por favor, sube tu archivo Excel consolidado en el panel lateral para continuar.")
