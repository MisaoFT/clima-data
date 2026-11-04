import io
import math
import numpy as np
import pandas as pd
import streamlit as st

# ==========================================
# CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Control de Calidad y Consolidado Kobo",
    page_icon="🌤️",
    layout="wide",
)

st.title("🌤️ Auditoría de Calidad y Consolidación Meteorológica")
st.markdown(
    "Sube tus archivos de KoboToolbox. El script purgará automáticamente las "
    "columnas redundantes, unificará los parámetros y calculará los acumulados "
    "y variables diarias derivadas."
)

# Panel lateral
st.sidebar.header("📁 Carga de Archivos CSV")
uploaded_files = st.sidebar.file_uploader(
    "Selecciona tus archivos de Kobo",
    type=["csv"],
    accept_multiple_files=True,
)


def purgar_columnas_one_hot(df: pd.DataFrame, start_idx: int, end_idx: int) -> pd.DataFrame:
    """
    Elimina rangos de columnas generados por preguntas de opción única en KoboToolbox.
    Soporta rangos por índices 0-indexed de columna.
    """
    if len(df.columns) > end_idx:
        cols_to_drop = df.columns[start_idx : end_idx + 1]
        return df.drop(columns=cols_to_drop)
    return df


def cargar_y_extraer_fecha(file_bytes) -> pd.DataFrame:
    """Lectura segura probando delimitadores ';' y ',' e indicando fecha base."""
    df = None
    for sep_test in [";", ","]:
        try:
            df_temp = pd.read_csv(
                io.BytesIO(file_bytes), sep=sep_test, on_bad_lines="skip"
            )
            if len(df_temp.columns) > 2:
                df = df_temp
                break
        except Exception:
            pass

    if df is None:
        df = pd.read_csv(
            io.BytesIO(file_bytes), sep=None, engine="python", on_bad_lines="skip"
        )

    if "start" in df.columns:
        df["fecha_start_clean"] = df["start"].astype(str).str[:10]
    else:
        df["fecha_start_clean"] = np.nan

    return df


def calcular_registro_unico_diario(p_list, hr_list, t_seca_media, nub_list, v_dir_list, v_vel_list):
    """
    Reduce las lecturas diarias a UN SOLO DATO representativo por variable.
    Aplica ponderación meteorológica, suma de vector viento y ecuación de Stull para Tw.
    """
    # 1. Presión y Humedad Ponderada (P07 + P13 + 2*P18) / 4
    p_valid = [v for v in p_list if pd.notnull(v)]
    if len(p_valid) == 3:
        p_diaria = round((p_valid[0] + p_valid[1] + (2 * p_valid[2])) / 4.0, 2)
    elif len(p_valid) > 0:
        p_diaria = round(float(np.mean(p_valid)), 2)
    else:
        p_diaria = np.nan

    hr_valid = [v for v in hr_list if pd.notnull(v)]
    if len(hr_valid) == 3:
        hr_diaria = round((hr_valid[0] + hr_valid[1] + (2 * hr_valid[2])) / 4.0, 1)
    elif len(hr_valid) > 0:
        hr_diaria = round(float(np.mean(hr_valid)), 1)
    else:
        hr_diaria = np.nan

    if pd.notnull(hr_diaria) and hr_diaria > 100.0:
        hr_diaria = 100.0

    # 2. Código de Nubosidad Diaria
    nub_valid = [v for v in nub_list if pd.notnull(v)]
    if len(nub_valid) > 0:
        suma_octas = sum(nub_valid)
        cod_nubosidad_diaria = 0 if suma_octas <= 6 else (1 if suma_octas <= 17 else 2)
    else:
        cod_nubosidad_diaria = np.nan

    # 3. Dirección del Viento Vectorial
    ve, vn = 0.0, 0.0
    valid_wind = False
    for d, v in zip(v_dir_list, v_vel_list):
        if pd.notnull(d) and pd.notnull(v):
            valid_wind = True
            rad = math.radians(d)
            ve += v * math.sin(rad)
            vn += v * math.cos(rad)

    if not valid_wind:
        dir_viento_diaria = np.nan
    elif ve == 0 and vn == 0:
        dir_viento_diaria = 0.0
    else:
        dir_viento_diaria = math.degrees(math.atan2(ve, vn))
        if dir_viento_diaria < 0:
            dir_viento_diaria += 360
        dir_viento_diaria = round(dir_viento_diaria, 1)

    # 4. Termómetro Húmedo (Stull, 2011)
    if pd.notnull(t_seca_media) and pd.notnull(hr_diaria):
        try:
            tw_diaria = (
                t_seca_media * math.atan(0.151977 * ((hr_diaria + 8.313659) ** 0.5))
                + math.atan(t_seca_media + hr_diaria)
                - math.atan(hr_diaria - 1.676331)
                + 0.00391838 * (hr_diaria ** 1.5) * math.atan(0.023101 * hr_diaria)
                - 4.686035
            )
            tw_diaria = round(tw_diaria, 1)
        except Exception:
            tw_diaria = np.nan
    else:
        tw_diaria = np.nan

    return {
        "Presion_Diaria_hPa": p_diaria,
        "Humedad_Diaria_Pct": hr_diaria,
        "Termometro_Humedo_Diario_C": tw_diaria,
        "Nubosidad_Diaria_Cod": cod_nubosidad_diaria,
        "Dir_Viento_Diaria_Deg": dir_viento_diaria,
    }


if uploaded_files:
    file_auto, file_clim, file_sino = None, None, None

    for uploaded_file in uploaded_files:
        fn_lower = uploaded_file.name.lower()
        if "automaticas" in fn_lower:
            file_auto = uploaded_file
        elif "climaticas" in fn_lower:
            file_clim = uploaded_file
        elif "sinopticas" in fn_lower:
            file_sino = uploaded_file

    st.sidebar.success("¡Archivos detectados!")
    st.sidebar.write(f"- **Automáticas:** {file_auto.name if file_auto else '❌'}")
    st.sidebar.write(f"- **Climáticas:** {file_clim.name if file_clim else '❌'}")
    st.sidebar.write(f"- **Sinópticas:** {file_sino.name if file_sino else '❌'}")

    if file_auto and file_clim and file_sino:
        if st.button("🚀 Procesar Datos y Generar Reporte"):
            with st.spinner("Procesando archivos y ejecutando control de calidad..."):

                # ----------------------------------------------------
                # PASO 1: CARGA Y PURGA DE COLUMNAS REDUNDANTES
                # ----------------------------------------------------
                # Automáticas: D a X -> índices 3 a 23
                raw_auto = cargar_y_extraer_fecha(file_auto.getvalue())
                raw_auto = purgar_columnas_one_hot(raw_auto, 3, 23)

                # Climáticas: D a BD -> índices 3 a 55
                raw_clim = cargar_y_extraer_fecha(file_clim.getvalue())
                raw_clim = purgar_columnas_one_hot(raw_clim, 3, 55)

                # Sinópticas: D a S -> índices 3 a 18
                raw_sino = cargar_y_extraer_fecha(file_sino.getvalue())
                raw_sino = purgar_columnas_one_hot(raw_sino, 3, 18)

                # ----------------------------------------------------
                # PASO 2: SELECCIÓN Y HOMOLOGACIÓN DE COLUMNAS
                # ----------------------------------------------------
                # Automáticas
                df_auto = raw_auto.reindex(
                    columns=[
                        "Nombre de la estación",
                        "Fecha",
                        "fecha_start_clean",
                        "Hora",
                        "Lluvia total:",
                        "Nubosidad",
                        "Direccion del viento:",
                        "Velocidad de viento",
                    ]
                ).copy()
                df_auto.columns = [
                    "estacion",
                    "fecha_manual",
                    "fecha_start",
                    "hora",
                    "lluvia",
                    "nub",
                    "dir_viento",
                    "vel_viento",
                ]
                for c in ["tseca", "tmin", "tmax", "hum_rel", "pre_atmos"]:
                    df_auto[c] = np.nan

                # Climáticas
                df_clim = raw_clim.reindex(
                    columns=[
                        "Nombre de la Estacion:",
                        "Fecha",
                        "fecha_start_clean",
                        "Hora",
                        "Temperatura Seca:",
                        "Temperatura minima:",
                        "Temperatura maxima:",
                        "Lluvia total:",
                        "Humedad Relativa:",
                        "Presion Atmosferica",
                        "Nubosidad",
                        "Direccion del viento:",
                        "Velocidad de viento",
                    ]
                ).copy()
                df_clim.columns = [
                    "estacion",
                    "fecha_manual",
                    "fecha_start",
                    "hora",
                    "tseca",
                    "tmin",
                    "tmax",
                    "lluvia",
                    "hum_rel",
                    "pre_atmos",
                    "nub",
                    "dir_viento",
                    "vel_viento",
                ]

                # Sinópticas
                df_sino = raw_sino.reindex(
                    columns=[
                        "estacion",
                        "Fecha",
                        "fecha_start_clean",
                        "Hora",
                        "tseca",
                        "tmin",
                        "tmax",
                        "lluvia",
                        "hum_rel",
                        "pre_atmos",
                        "nub",
                        "dir_viento",
                        "vel_viento",
                    ]
                ).copy()
                df_sino.columns = [
                    "estacion",
                    "fecha_manual",
                    "fecha_start",
                    "hora",
                    "tseca",
                    "tmin",
                    "tmax",
                    "lluvia",
                    "hum_rel",
                    "pre_atmos",
                    "nub",
                    "dir_viento",
                    "vel_viento",
                ]

                # Unificación
                df_unificado = pd.concat([df_auto, df_clim, df_sino], ignore_index=True)

                # ----------------------------------------------------
                # PASO 3: ESTANDARIZACIÓN DE TIPOS Y FECHAS
                # ----------------------------------------------------
                df_unificado["estacion_std"] = (
                    df_unificado["estacion"]
                    .astype(str)
                    .str.strip()
                    .str.upper()
                    .str.replace("_", " ")
                )

                def parsear_fechas_seguro(serie_fechas):
                    dt_iso = pd.to_datetime(
                        serie_fechas, format="%Y-%m-%d", errors="coerce"
                    )
                    dt_lat = pd.to_datetime(
                        serie_fechas, format="%d/%m/%Y", errors="coerce"
                    )
                    return dt_iso.fillna(dt_lat)

                df_unificado["f_manual_dt"] = parsear_fechas_seguro(
                    df_unificado["fecha_manual"]
                )
                df_unificado["f_start_dt"] = parsear_fechas_seguro(
                    df_unificado["fecha_start"]
                )

                df_unificado["fecha_dt"] = df_unificado["f_manual_dt"].fillna(
                    df_unificado["f_start_dt"]
                )
                df_unificado["fecha_dt"] = df_unificado.groupby("estacion_std")[
                    "fecha_dt"
                ].transform(lambda x: x.ffill().bfill())

                df_unificado["hora_std"] = (
                    df_unificado["hora"]
                    .astype(str)
                    .str.replace("_", ":")
                    .str.strip()
                )
                df_unificado["hora_std"] = df_unificado["hora_std"].apply(
                    lambda x: f"0{x}" if len(x) == 4 and x.endswith(":00") else x
                )

                numeric_cols = [
                    "tseca",
                    "tmin",
                    "tmax",
                    "lluvia",
                    "hum_rel",
                    "pre_atmos",
                    "nub",
                    "dir_viento",
                    "vel_viento",
                ]
                for col in numeric_cols:
                    df_unificado[col] = pd.to_numeric(df_unificado[col], errors="coerce")

                def fmt_fecha(dt):
                    return dt.strftime("%Y-%m-%d") if pd.notnull(dt) else "Fecha Nula"

                df_unificado["fecha_str"] = df_unificado["fecha_dt"].apply(fmt_fecha)

                # ----------------------------------------------------
                # PASO 4: CONSOLIDACIÓN Y CÁLCULO DE VARIABLES
                # ----------------------------------------------------
                registros_consolidados = []
                grupos = df_unificado.groupby(["estacion_std", "fecha_dt"], dropna=False)

                for (estacion, fecha), group in grupos:
                    # Lecturas tri-horarias
                    t_07 = group[group["hora_std"] == "07:00"]["tseca"].values
                    t_13 = group[group["hora_std"] == "13:00"]["tseca"].values
                    t_18 = group[group["hora_std"] == "18:00"]["tseca"].values

                    val_07 = t_07[0] if len(t_07) > 0 and pd.notnull(t_07[0]) else None
                    val_13 = t_13[0] if len(t_13) > 0 and pd.notnull(t_13[0]) else None
                    val_18 = t_18[0] if len(t_18) > 0 and pd.notnull(t_18[0]) else None

                    if val_07 is not None and val_13 is not None and val_18 is not None:
                        tmed = round((val_07 + val_13 + val_18) / 3.0, 1)
                    else:
                        valid_t = group["tseca"].dropna()
                        tmed = round(float(valid_t.mean()), 1) if not valid_t.empty else np.nan

                    tmin_dia = group["tmin"].min()
                    tmax_dia = group["tmax"].max()
                    lluvia_total = group["lluvia"].sum(min_count=1)

                    # Listas tri-horarias para variables ponderadas
                    def get_tri_list(col_name):
                        res = []
                        for h in ["07:00", "13:00", "18:00"]:
                            vals = group[group["hora_std"] == h][col_name].values
                            res.append(vals[0] if len(vals) > 0 else np.nan)
                        return res

                    p_list = get_tri_list("pre_atmos")
                    hr_list = get_tri_list("hum_rel")
                    nub_list = get_tri_list("nub")
                    v_dir_list = get_tri_list("dir_viento")
                    v_vel_list = get_tri_list("vel_viento")

                    # Ejecución de la función reductora
                    dict_derivadas = calcular_registro_unico_diario(
                        p_list=p_list,
                        hr_list=hr_list,
                        t_seca_media=tmed,
                        nub_list=nub_list,
                        v_dir_list=v_dir_list,
                        v_vel_list=v_vel_list,
                    )

                    reg = {
                        "Estacion": estacion,
                        "Fecha": fmt_fecha(fecha),
                        "TMED": tmed,
                        "TMIN": tmin_dia if pd.notnull(tmin_dia) else np.nan,
                        "TMAX": tmax_dia if pd.notnull(tmax_dia) else np.nan,
                        "LLUVIA_ACUM": lluvia_total if pd.notnull(lluvia_total) else np.nan,
                    }
                    reg.update(dict_derivadas)
                    registros_consolidados.append(reg)

                df_consolidado = pd.DataFrame(registros_consolidados)

                # Generación de Excel para Descarga
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_consolidado.to_excel(writer, index=False, sheet_name="Consolidado")
                excel_data = output.getvalue()

                st.success("✅ ¡Procesamiento completado con éxito!")
                st.download_button(
                    label="📥 Descargar Archivo Excel Consolidado",
                    data=excel_data,
                    file_name="consolidado_kobo_valido.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

                # ----------------------------------------------------
                # PASO 5: REPORTE Y CONTROL DE CALIDAD
                # ----------------------------------------------------
                st.subheader("🚨 Reporte Detallado de Control de Calidad")
                inc_tmin = df_unificado[
                    (df_unificado["tmin"].notnull())
                    & (df_unificado["tseca"].notnull())
                    & (df_unificado["tmin"] >= df_unificado["tseca"])
                ]
                inc_tmax = df_unificado[
                    (df_unificado["tmax"].notnull())
                    & (df_unificado["tseca"].notnull())
                    & (df_unificado["tmax"] <= df_unificado["tseca"])
                ]
                ex_lluvia = df_unificado[df_unificado["lluvia"] > 40]
                ex_tmax = df_unificado[df_unificado["tmax"] > 42]
                ex_tmin = df_unificado[df_unificado["tmin"] < 0]

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Alertas de Lluvia (>40mm)", len(ex_lluvia))
                with col2:
                    st.metric(
                        "Alertas de Temperatura (Inconsistencias/Extremas)",
                        len(inc_tmin) + len(inc_tmax) + len(ex_tmax) + len(ex_tmin),
                    )

                with st.expander(f"⚠️ Inconsistencias Físicas: Tmin >= Tseca ({len(inc_tmin)} casos)"):
                    if not inc_tmin.empty:
                        st.dataframe(
                            inc_tmin[["estacion_std", "fecha_str", "hora_std", "tmin", "tseca"]],
                            use_container_width=True,
                        )
                    else:
                        st.success("No hay registros con Tmin mayor o igual a Tseca.")

                with st.expander(f"⚠️ Inconsistencias Físicas: Tmax <= Tseca ({len(inc_tmax)} casos)"):
                    if not inc_tmax.empty:
                        st.dataframe(
                            inc_tmax[["estacion_std", "fecha_str", "hora_std", "tmax", "tseca"]],
                            use_container_width=True,
                        )
                    else:
                        st.success("No hay registros con Tmax menor o igual a Tseca.")
    else:
        st.info("Por favor asegúrate de subir los tres archivos (Automáticas, Climáticas y Sinópticas).")
else:
    st.info("👈 Comienza subiendo tus archivos CSV en el panel lateral.")