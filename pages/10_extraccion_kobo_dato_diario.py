import io
import math
import numpy as np
import pandas as pd
import streamlit as st

# ==========================================
# CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Control de calidad y unificación de datos desde KoboCollect",
    page_icon="🌤️",
    layout="wide",
)

st.title("🌤️ Auditoría de calidad de datos diarios preliminares y unificación de archivos - INSIVUMEH")
st.markdown(
    "Plantilla base de procesamiento: Sube tus archivos de KoboToolbox: Estaciones climaticas, sinópticas y automáticas para: "
    "unificar variables meteorológicas, formatear selecciones múltiples de fenómenos, "
    "aplicar ajustes de formato y escala (octas 0-8, rumbo vectorial, humedad entera) "
    "visualizar las alertas de temperatura y lluvia"
    " auditar inconsistencias físicas y descargar el archivo"
)

# Panel lateral
st.sidebar.header("📁 Carga de archivos en formato .CSV")
uploaded_files = st.sidebar.file_uploader(
    "Selecciona tus archivos de Kobo",
    type=["csv"],
    accept_multiple_files=True,
)

# Mapeo de códigos numéricos KoboToolbox a descripción formal
MAPEO_CODIGOS_FENOMENOS = {
    "0": "0) Ninguno",
    "1": "1) Visibilidad baja por bruma/humo",
    "2": "2) Relámpagos lejanos sin truenos",
    "3": "3) Tormenta eléctrica",
    "4": "4) Niebla",
    "5": "5) Llovizna",
    "6": "6) Lluvia",
    "7": "7) Aguacero",
    "8": "8) Granizo",
    "9": "9) Rocío",
    "10": "10) Helada",
}


def purgar_columnas_one_hot(df: pd.DataFrame, start_idx: int, end_idx: int) -> pd.DataFrame:
    """Elimina columnas desglosadas (One-Hot) creadas por KoboToolbox."""
    if len(df.columns) > end_idx:
        cols_to_drop = df.columns[start_idx : end_idx + 1]
        return df.drop(columns=cols_to_drop)
    return df


def cargar_y_extraer_fecha(file_bytes) -> pd.DataFrame:
    """Lectura resiliente probando delimitadores ';' y ','."""
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


def parsear_fenomenos_multiselect(serie_fenomenos: pd.Series) -> str:
    """
    Parsea celdas con selección múltiple de Kobo (ej: '9 1', '4 9')
    y las traduce a sus nombres descriptivos sin duplicados.
    """
    lista_limpia = []
    for val in serie_fenomenos.dropna():
        val_str = str(val).strip()
        if not val_str or val_str.lower() in ["nan", "none"]:
            continue

        parts = val_str.split()
        # Si son códigos numéricos separados por espacios
        if all(p.isdigit() for p in parts):
            for p in parts:
                desc = MAPEO_CODIGOS_FENOMENOS.get(p, p)
                if desc not in lista_limpia:
                    lista_limpia.append(desc)
        else:
            if val_str not in lista_limpia:
                lista_limpia.append(val_str)

    if not lista_limpia:
        return "Ninguno"
    return " | ".join(lista_limpia)


def ajustar_rumbo_cardinal_grados(grados: float) -> float:
    """Ajusta un ángulo continuo al rumbo cardinal estándar más cercano."""
    if pd.isnull(grados):
        return np.nan
    rumbos_estandar = [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0, 360.0]
    return min(rumbos_estandar, key=lambda r: abs(r - grados))


def calcular_registro_unico_diario(p_list, hr_list, t_seca_media, nub_list, v_dir_list, v_vel_list):
    """Calcula datos diarios ponderados aplicando formatos INSIVUMEH."""
    # 1. Presión Ponderada a 1 decimal
    p_valid = [v for v in p_list if pd.notnull(v)]
    if len(p_valid) == 3:
        p_diaria = round((p_valid[0] + p_valid[1] + (2 * p_valid[2])) / 4.0, 1)
    elif len(p_valid) > 0:
        p_diaria = round(float(np.mean(p_valid)), 1)
    else:
        p_diaria = np.nan

    # 2. Humedad Relativa Ponderada como Número Entero
    hr_valid = [v for v in hr_list if pd.notnull(v)]
    if len(hr_valid) == 3:
        hr_calc = (hr_valid[0] + hr_valid[1] + (2 * hr_valid[2])) / 4.0
        hr_diaria = float(round(hr_calc, 0))
    elif len(hr_valid) > 0:
        hr_diaria = float(round(float(np.mean(hr_valid)), 0))
    else:
        hr_diaria = np.nan

    if pd.notnull(hr_diaria) and hr_diaria > 100.0:
        hr_diaria = 100.0

    # 3. Nubosidad Diaria Representativa en Octas (0 a 8)
    nub_valid = [v for v in nub_list if pd.notnull(v)]
    if len(nub_valid) > 0:
        octas_media = round(float(np.mean(nub_valid)), 0)
        octas_media = max(0.0, min(8.0, octas_media))
        cod_nubosidad_diaria = float(octas_media)
    else:
        cod_nubosidad_diaria = np.nan

    # 4. Vector Viento
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
        grados_calculados = math.degrees(math.atan2(ve, vn))
        if grados_calculados < 0:
            grados_calculados += 360
        dir_viento_diaria = ajustar_rumbo_cardinal_grados(grados_calculados)

    # 5. Termómetro Húmedo (Stull)
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

                # PASO 1: CARGA Y PURGA DE COLUMNAS ONE-HOT
                raw_auto = cargar_y_extraer_fecha(file_auto.getvalue())
                raw_auto = purgar_columnas_one_hot(raw_auto, 3, 23)

                raw_clim = cargar_y_extraer_fecha(file_clim.getvalue())
                raw_clim = purgar_columnas_one_hot(raw_clim, 3, 55)

                raw_sino = cargar_y_extraer_fecha(file_sino.getvalue())
                raw_sino = purgar_columnas_one_hot(raw_sino, 3, 18)

                # PASO 2: HOMOLOGACIÓN Y SELECCIÓN DE COLUMNAS
                df_auto = raw_auto.reindex(
                    columns=[
                        "Nombre de la estación", "Fecha", "fecha_start_clean", "Hora",
                        "Lluvia total:", "Nubosidad", "Direccion del viento:",
                        "Velocidad de viento", "Evaporacion de Tanque", "Fenomenos"
                    ]
                ).copy()
                df_auto.columns = [
                    "estacion", "fecha_manual", "fecha_start", "hora",
                    "lluvia", "nub", "dir_viento", "vel_viento", "eva_tanque", "fenomenos"
                ]
                for c in ["tseca", "tmin", "tmax", "hum_rel", "pre_atmos", "eva_piche", "bri_solar", "rad_solar", "tsuelo_5", "tsuelo_50", "tsuelo_100"]:
                    df_auto[c] = np.nan

                df_clim = raw_clim.reindex(
                    columns=[
                        "Nombre de la Estacion:", "Fecha", "fecha_start_clean", "Hora",
                        "Temperatura Seca:", "Temperatura minima:", "Temperatura maxima:",
                        "Lluvia total:", "Humedad Relativa:", "Presion Atmosferica",
                        "Nubosidad", "Direccion del viento:", "Velocidad de viento",
                        "Evaporacion de Tanque", "Evaporacion de Piche", "Brillo Solar",
                        "Temperatura Suelo 5cm", "Temperatura Suelo 50cm", "Temperatura Suelo 100cm", "Fenomenos"
                    ]
                ).copy()
                df_clim.columns = [
                    "estacion", "fecha_manual", "fecha_start", "hora",
                    "tseca", "tmin", "tmax", "lluvia", "hum_rel", "pre_atmos",
                    "nub", "dir_viento", "vel_viento", "eva_tanque", "eva_piche",
                    "bri_solar", "tsuelo_5", "tsuelo_50", "tsuelo_100", "fenomenos"
                ]
                df_clim["rad_solar"] = np.nan

                df_sino = raw_sino.reindex(
                    columns=[
                        "estacion", "Fecha", "fecha_start_clean", "Hora",
                        "tseca", "tmin", "tmax", "lluvia", "hum_rel", "pre_atmos",
                        "nub", "dir_viento", "vel_viento", "eva_tan", "bri_solar",
                        "rad_solar", "tsuelo_100", "Fenomenos"
                    ]
                ).copy()
                df_sino.columns = [
                    "estacion", "fecha_manual", "fecha_start", "hora",
                    "tseca", "tmin", "tmax", "lluvia", "hum_rel", "pre_atmos",
                    "nub", "dir_viento", "vel_viento", "eva_tanque", "bri_solar",
                    "rad_solar", "tsuelo_100", "fenomenos"
                ]
                for c in ["eva_piche", "tsuelo_5", "tsuelo_50"]:
                    df_sino[c] = np.nan

                df_unificado = pd.concat([df_auto, df_clim, df_sino], ignore_index=True)

                # PASO 3: ESTANDARIZACIÓN
                df_unificado["estacion_std"] = (
                    df_unificado["estacion"]
                    .astype(str)
                    .str.strip()
                    .str.upper()
                    .str.replace("_", " ")
                )

                def parsear_fechas_seguro(serie_fechas):
                    dt_iso = pd.to_datetime(serie_fechas, format="%Y-%m-%d", errors="coerce")
                    dt_lat = pd.to_datetime(serie_fechas, format="%d/%m/%Y", errors="coerce")
                    return dt_iso.fillna(dt_lat)

                df_unificado["f_manual_dt"] = parsear_fechas_seguro(df_unificado["fecha_manual"])
                df_unificado["f_start_dt"] = parsear_fechas_seguro(df_unificado["fecha_start"])
                df_unificado["fecha_dt"] = df_unificado["f_manual_dt"].fillna(df_unificado["f_start_dt"])
                df_unificado["fecha_dt"] = df_unificado.groupby("estacion_std")["fecha_dt"].transform(
                    lambda x: x.ffill().bfill()
                )

                df_unificado["hora_std"] = (
                    df_unificado["hora"].astype(str).str.replace("_", ":").str.strip()
                )
                df_unificado["hora_std"] = df_unificado["hora_std"].apply(
                    lambda x: f"0{x}" if len(x) == 4 and x.endswith(":00") else x
                )

                numeric_cols = [
                    "tseca", "tmin", "tmax", "lluvia", "hum_rel", "pre_atmos",
                    "nub", "dir_viento", "vel_viento", "eva_tanque", "eva_piche",
                    "bri_solar", "rad_solar", "tsuelo_5", "tsuelo_50", "tsuelo_100"
                ]
                for col in numeric_cols:
                    df_unificado[col] = pd.to_numeric(df_unificado[col], errors="coerce")

                def fmt_fecha(dt):
                    return dt.strftime("%Y-%m-%d") if pd.notnull(dt) else "Fecha Nula"

                df_unificado["fecha_str"] = df_unificado["fecha_dt"].apply(fmt_fecha)

                # PASO 4: CONSOLIDACIÓN DIARIA
                registros_consolidados = []
                grupos = df_unificado.groupby(["estacion_std", "fecha_dt"], dropna=False)

                for (estacion, fecha), group in grupos:
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

                    g_07 = group[group["hora_std"] == "07:00"]
                    eva_tanque_val = g_07["eva_tanque"].values[0] if not g_07.empty and pd.notnull(g_07["eva_tanque"].values[0]) else (group["eva_tanque"].dropna().iloc[0] if not group["eva_tanque"].dropna().empty else np.nan)
                    eva_piche_val = g_07["eva_piche"].values[0] if not g_07.empty and pd.notnull(g_07["eva_piche"].values[0]) else (group["eva_piche"].dropna().iloc[0] if not group["eva_piche"].dropna().empty else np.nan)

                    g_18 = group[group["hora_std"] == "18:00"]
                    brillo_solar_val = g_18["bri_solar"].values[0] if not g_18.empty and pd.notnull(g_18["bri_solar"].values[0]) else group["bri_solar"].max()
                    rad_solar_val = g_18["rad_solar"].values[0] if not g_18.empty and pd.notnull(g_18["rad_solar"].values[0]) else group["rad_solar"].max()

                    tsuelo_5_val = round(float(group["tsuelo_5"].dropna().mean()), 1) if not group["tsuelo_5"].dropna().empty else np.nan
                    tsuelo_50_val = round(float(group["tsuelo_50"].dropna().mean()), 1) if not group["tsuelo_50"].dropna().empty else np.nan
                    tsuelo_100_val = round(float(group["tsuelo_100"].dropna().mean()), 1) if not group["tsuelo_100"].dropna().empty else np.nan

                    # Parseo de múltiples fenómenos Kobo (ej: '9 1' -> '9) Rocío | 1) Visibilidad baja...')
                    fenomenos_val = parsear_fenomenos_multiselect(group["fenomenos"])

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
                        "EVAPORACION_TANQUE_07H": eva_tanque_val if pd.notnull(eva_tanque_val) else np.nan,
                        "EVAPORACION_PICHE_07H": eva_piche_val if pd.notnull(eva_piche_val) else np.nan,
                        "BRILLO_SOLAR_18H": brillo_solar_val if pd.notnull(brillo_solar_val) else np.nan,
                        "RADIACION_SOLAR": rad_solar_val if pd.notnull(rad_solar_val) else np.nan,
                        "TSUELO_5CM": tsuelo_5_val,
                        "TSUELO_50CM": tsuelo_50_val,
                        "TSUELO_100CM": tsuelo_100_val,
                        "FENOMENOS": fenomenos_val,
                    }
                    reg.update(dict_derivadas)
                    registros_consolidados.append(reg)

                df_consolidado = pd.DataFrame(registros_consolidados)

                columnas_ordenadas = [
                    "Estacion", "Fecha", "TMED", "TMIN", "TMAX", "LLUVIA_ACUM",
                    "Presion_Diaria_hPa", "Humedad_Diaria_Pct", "Termometro_Humedo_Diario_C",
                    "Nubosidad_Diaria_Cod", "Dir_Viento_Diaria_Deg",
                    "EVAPORACION_TANQUE_07H", "EVAPORACION_PICHE_07H", "BRILLO_SOLAR_18H",
                    "RADIACION_SOLAR", "TSUELO_5CM", "TSUELO_50CM", "TSUELO_100CM", "FENOMENOS"
                ]
                df_consolidado = df_consolidado.reindex(columns=columnas_ordenadas)

                # Generar Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_consolidado.to_excel(writer, index=False, sheet_name="Consolidado")
                excel_data = output.getvalue()

                st.success("✅ ¡Procesamiento completado con éxito!")
                st.download_button(
                    label="📥 Descargar archivo excel unificado y revisado",
                    data=excel_data,
                    file_name="dato_diario_unificado_kobo.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

                # PASO 5: REPORTE CONTROL DE CALIDAD
                st.subheader("🚨 Reporte detallado de Control de Calidad")
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

                with st.expander(f"⚠️ Inconsistencias Físicas: Tmin >= Tseca ({len(inc_tmin)} casos)", expanded=True):
                    if not inc_tmin.empty:
                        st.dataframe(inc_tmin[["estacion_std", "fecha_str", "hora_std", "tmin", "tseca"]], use_container_width=True)
                    else:
                        st.success("No hay registros con Tmin mayor o igual a Tseca.")

                with st.expander(f"⚠️ Inconsistencias Físicas: Tmax <= Tseca ({len(inc_tmax)} casos)", expanded=True):
                    if not inc_tmax.empty:
                        st.dataframe(inc_tmax[["estacion_std", "fecha_str", "hora_std", "tmax", "tseca"]], use_container_width=True)
                    else:
                        st.success("No hay registros con Tmax menor o igual a Tseca.")

                with st.expander(f"🌧️ Lluvias Extremas (> 40 mm) ({len(ex_lluvia)} casos)", expanded=True):
                    if not ex_lluvia.empty:
                        st.dataframe(ex_lluvia[["estacion_std", "fecha_str", "hora_std", "lluvia"]], use_container_width=True)
                    else:
                        st.success("No hay registros de lluvia extrema.")

                with st.expander(f"🔥 Temperaturas Máximas Extremas (> 42 °C) ({len(ex_tmax)} casos)", expanded=True):
                    if not ex_tmax.empty:
                        st.dataframe(ex_tmax[["estacion_std", "fecha_str", "hora_std", "tmax"]], use_container_width=True)
                    else:
                        st.success("No hay registros de temperaturas máximas extremas.")

                with st.expander(f"❄️ Temperaturas Mínimas Extremas (< 0 °C) ({len(ex_tmin)} casos)", expanded=True):
                    if not ex_tmin.empty:
                        st.dataframe(ex_tmin[["estacion_std", "fecha_str", "hora_std", "tmin"]], use_container_width=True)
                    else:
                        st.success("No hay registros de temperaturas mínimas bajo el punto de congelación.")

    else:
        st.info("Por favor asegúrate de subir los tres archivos (Automáticas, Climáticas y Sinópticas) en el menú lateral.")
else:
    st.info("👈 Comienza subiendo tus archivos CSV en el panel lateral para habilitar la auditoría y descarga.")
