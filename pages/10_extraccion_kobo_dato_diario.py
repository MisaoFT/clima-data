import io
import math
import numpy as np
import pandas as pd
import streamlit as st

# ==========================================
# CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Control de Calidad y unificación de archivos KoboCollect",
    page_icon="🌤️",
    layout="wide",
)

st.title("🌤️ Control de calidad visual y consolidación meteorológica para el dato diario preliminar INSIVUMEH")
st.markdown(
    "Procesamiento diario, semanal o mensual de formularios KoboToolbox: "
    "Revisión y visualización de datos climaticos para su revisión visual "
    "Este proceso se realiza diariamente desde las 7 de la mañana de cada día los 365 días del año."
)

# ==========================================
# PANEL LATERAL: CARGA Y CONFIGURACIÓN
# ==========================================
st.sidebar.header("📁 Carga de archivos CSV desde KoboCollect")
uploaded_files = st.sidebar.file_uploader(
    "Selecciona tus archivos de formularios de Kobo (Automáticas, Climáticas, Sinópticas)",
    type=["csv"],
    accept_multiple_files=True,
)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Configuración horaria")
desplazar_lluvia_en_consolidado = st.sidebar.checkbox(
    "Asignar lluvia de las 07:00 al día anterior en el Consolidado",
    value=True,
    help="Alinea la lluvia medida a las 07:00 AM con la fecha meteorológica real (ayer), igualándola con TMAX y TMIN."
)

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


def limpiar_columnas_kobo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia espacios en nombres de columnas y elimina únicamente las columnas
    desglosadas One-Hot (que contienen '/') sin depender de posiciones fijas.
    Esto evita perder columnas cuando se descargan semanas o meses con múltiples versiones.
    """
    df.columns = [str(c).strip() for c in df.columns]
    cols_validas = [c for c in df.columns if "/" not in c]
    return df[cols_validas].copy()


def extraer_fecha_local_gt(serie_timestamps: pd.Series) -> pd.Series:
    """
    Convierte timestamps ISO de Kobo (con -06:00 o en UTC Z/+00:00)
    a hora local exacta de Guatemala (America/Guatemala, UTC-6).
    """
    dt_utc = pd.to_datetime(serie_timestamps, errors="coerce", utc=True)
    dt_gt = dt_utc.dt.tz_convert("America/Guatemala")
    return dt_gt.dt.tz_localize(None)


def cargar_csv_resiliente(file_bytes) -> pd.DataFrame:
    """Lectura resiliente probando codificaciones (UTF-8 / Latin-1) y delimitadores (';' / ',')."""
    df = None
    for enc in ["utf-8-sig", "utf-8", "latin1"]:
        for sep_test in [";", ","]:
            try:
                df_temp = pd.read_csv(
                    io.BytesIO(file_bytes),
                    sep=sep_test,
                    encoding=enc,
                    on_bad_lines="skip",
                    dtype=str,  # Leer como texto primero evita corrupción de fechas y ceros
                )
                if len(df_temp.columns) > 2:
                    df = df_temp
                    break
            except Exception:
                continue
        if df is not None:
            break

    if df is None:
        df = pd.read_csv(
            io.BytesIO(file_bytes),
            sep=None,
            engine="python",
            on_bad_lines="skip",
            dtype=str,
        )

    df = limpiar_columnas_kobo(df)

    # Extraer timestamp local Guatemala (UTC-6)
    if "start" in df.columns:
        df["start_gt_dt"] = extraer_fecha_local_gt(df["start"])
    elif "_submission_time" in df.columns:
        df["start_gt_dt"] = extraer_fecha_local_gt(df["_submission_time"])
    else:
        df["start_gt_dt"] = pd.NaT

    return df


def parsear_fechas_flexible(serie_fechas: pd.Series) -> pd.Series:
    """
    Soporta múltiples formatos de fecha que aparecen en exportaciones semanales/mensuales:
    YYYY-MM-DD, DD/MM/YYYY, YYYY/MM/DD, DD-MM-YYYY y timestamps completos.
    """
    s_clean = serie_fechas.astype(str).str.strip()
    s_clean = s_clean.replace({"nan": np.nan, "None": np.nan, "NaT": np.nan, "": np.nan})

    # Extraer solo la parte de fecha si trae hora pegada (ej. '2026-11-03 07:00:00')
    s_date_part = s_clean.str.split(" ").str[0].str.split("T").str[0]

    # 1. Formato ISO estándar YYYY-MM-DD
    dt_iso = pd.to_datetime(s_date_part, format="%Y-%m-%d", errors="coerce")
    # 2. Formato Latinoamericano DD/MM/YYYY
    dt_lat = pd.to_datetime(s_date_part, format="%d/%m/%Y", errors="coerce")
    # 3. Formato con barras YYYY/MM/DD
    dt_iso_slash = pd.to_datetime(s_date_part, format="%Y/%m/%d", errors="coerce")
    # 4. Formato con guiones DD-MM-YYYY
    dt_lat_dash = pd.to_datetime(s_date_part, format="%d-%m-%Y", errors="coerce")
    # 5. Fallback general con dayfirst=True
    dt_mixed = pd.to_datetime(s_date_part, dayfirst=True, errors="coerce")

    return (
        dt_iso.fillna(dt_lat)
        .fillna(dt_iso_slash)
        .fillna(dt_lat_dash)
        .fillna(dt_mixed)
        .dt.normalize()
    )


def limpiar_numero_resiliente(serie: pd.Series) -> pd.Series:
    """Convierte a numérico aceptando tanto punto (12.5) como coma decimal (12,5)."""
    s = serie.astype(str).str.strip().str.replace(",", ".", regex=False)
    s = s.replace({"nan": np.nan, "None": np.nan, "": np.nan, "NaN": np.nan})
    return pd.to_numeric(s, errors="coerce")


def normalizar_hora(serie_hora: pd.Series) -> pd.Series:
    """Estandariza formatos de hora ('7_00', '7:00', '07:00:00', '7') a '07:00', '13:00', '18:00'."""
    def _fmt_h(val):
        if pd.isnull(val):
            return ""
        s = str(val).strip().replace("_", ":")
        if s in ["nan", "None", ""]:
            return ""
        # Si viene como '07:00:00', tomar '07:00'
        parts = s.split(":")
        if len(parts) >= 2 and parts[0].isdigit():
            return f"{int(parts[0]):02d}:{parts[1][:2]}"
        if s.isdigit():
            return f"{int(s):02d}:00"
        return s

    return serie_hora.apply(_fmt_h)


def parsear_fenomenos_multiselect(serie_fenomenos: pd.Series) -> str:
    """Parsea celdas con selección múltiple de Kobo (ej: '9 1', '4 9')."""
    lista_limpia = []
    for val in serie_fenomenos.dropna():
        val_str = str(val).strip()
        if not val_str or val_str.lower() in ["nan", "none"]:
            continue

        parts = val_str.split()
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


def seleccionar_columnas_seguro(df_raw: pd.DataFrame, mapa_columnas: dict) -> pd.DataFrame:
    """
    Extrae columnas buscando coincidencias exactas o sin dos puntos finales,
    sin depender del orden de las columnas en el CSV.
    """
    cols_lower_map = {c.lower().rstrip(":"): c for c in df_raw.columns}
    resultado = pd.DataFrame(index=df_raw.index)

    for col_destino, col_origen in mapa_columnas.items():
        if col_origen in df_raw.columns:
            resultado[col_destino] = df_raw[col_origen]
        else:
            clave_norm = col_origen.lower().rstrip(":")
            if clave_norm in cols_lower_map:
                resultado[col_destino] = df_raw[cols_lower_map[clave_norm]]
            else:
                resultado[col_destino] = np.nan
    return resultado


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
        # ----------------------------------------------------
        # PASO 1: CARGA RESILIENTE (SIN BORRADO POSICIONAL)
        # ----------------------------------------------------
        raw_auto = cargar_csv_resiliente(file_auto.getvalue())
        raw_clim = cargar_csv_resiliente(file_clim.getvalue())
        raw_sino = cargar_csv_resiliente(file_sino.getvalue())

        # PASO 2: HOMOLOGACIÓN POR NOMBRE DE COLUMNA
        df_auto = seleccionar_columnas_seguro(
            raw_auto,
            {
                "estacion": "Nombre de la estación",
                "fecha_manual": "Fecha",
                "start_gt_dt": "start_gt_dt",
                "hora": "Hora",
                "lluvia": "Lluvia total:",
                "nub": "Nubosidad",
                "dir_viento": "Direccion del viento:",
                "vel_viento": "Velocidad de viento",
                "eva_tanque": "Evaporacion de Tanque",
                "fenomenos": "Fenomenos",
            },
        )
        for c in ["tseca", "tmin", "tmax", "hum_rel", "pre_atmos", "eva_piche", "bri_solar", "rad_solar", "tsuelo_5", "tsuelo_50", "tsuelo_100"]:
            df_auto[c] = np.nan

        df_clim = seleccionar_columnas_seguro(
            raw_clim,
            {
                "estacion": "Nombre de la Estacion:",
                "fecha_manual": "Fecha",
                "start_gt_dt": "start_gt_dt",
                "hora": "Hora",
                "tseca": "Temperatura Seca:",
                "tmin": "Temperatura minima:",
                "tmax": "Temperatura maxima:",
                "lluvia": "Lluvia total:",
                "hum_rel": "Humedad Relativa:",
                "pre_atmos": "Presion Atmosferica",
                "nub": "Nubosidad",
                "dir_viento": "Direccion del viento:",
                "vel_viento": "Velocidad de viento",
                "eva_tanque": "Evaporacion de Tanque",
                "eva_piche": "Evaporacion de Piche",
                "bri_solar": "Brillo Solar",
                "tsuelo_5": "Temperatura Suelo 5cm",
                "tsuelo_50": "Temperatura Suelo 50cm",
                "tsuelo_100": "Temperatura Suelo 100cm",
                "fenomenos": "Fenomenos",
            },
        )
        df_clim["rad_solar"] = np.nan

        df_sino = seleccionar_columnas_seguro(
            raw_sino,
            {
                "estacion": "estacion",
                "fecha_manual": "Fecha",
                "start_gt_dt": "start_gt_dt",
                "hora": "Hora",
                "tseca": "tseca",
                "tmin": "tmin",
                "tmax": "tmax",
                "lluvia": "lluvia",
                "hum_rel": "hum_rel",
                "pre_atmos": "pre_atmos",
                "nub": "nub",
                "dir_viento": "dir_viento",
                "vel_viento": "vel_viento",
                "eva_tanque": "eva_tan",
                "bri_solar": "bri_solar",
                "rad_solar": "rad_solar",
                "tsuelo_100": "tsuelo_100",
                "fenomenos": "Fenomenos",
            },
        )
        for c in ["eva_piche", "tsuelo_5", "tsuelo_50"]:
            df_sino[c] = np.nan

        df_unificado = pd.concat([df_auto, df_clim, df_sino], ignore_index=True)

        # PASO 3: ESTANDARIZACIÓN HORARIA Y DE FECHAS
        df_unificado["estacion_std"] = (
            df_unificado["estacion"]
            .astype(str)
            .str.strip()
            .str.upper()
            .str.replace("_", " ")
        )
        df_unificado = df_unificado[
            ~df_unificado["estacion_std"].isin(["NAN", "NONE", ""])
        ].copy()

        df_unificado["hora_std"] = normalizar_hora(df_unificado["hora"])
        df_unificado["f_manual_dt"] = parsear_fechas_flexible(df_unificado["fecha_manual"])
        df_unificado["f_start_gt_date"] = pd.to_datetime(
            df_unificado["start_gt_dt"], errors="coerce"
        ).dt.normalize()

        # Rescate de envíos tardíos (turno 18:00 enviado de madrugada GT)
        mask_tarde_18 = (
            df_unificado["f_manual_dt"].isnull()
            & (df_unificado["hora_std"] == "18:00")
            & (pd.to_datetime(df_unificado["start_gt_dt"], errors="coerce").dt.hour < 8)
        )
        df_unificado.loc[mask_tarde_18, "f_start_gt_date"] -= pd.Timedelta(days=1)

        # Prioridad: Fecha manual -> Fecha timestamp local GT (nunca propagar fechas entre días distintos)
        df_unificado["fecha_dt"] = df_unificado["f_manual_dt"].fillna(
            df_unificado["f_start_gt_date"]
        )

        # Filtro opcional de rango de fechas (ideal para revisar semanas o meses)
        fechas_validas = df_unificado["fecha_dt"].dropna()
        if not fechas_validas.empty:
            min_f = fechas_validas.min().date()
            max_f = fechas_validas.max().date()
            st.sidebar.markdown("---")
            st.sidebar.header("📅 Rango de Fechas Detectado")
            st.sidebar.info(f"Datos disponibles: **{min_f}** al **{max_f}**")
            rango_seleccionado = st.sidebar.date_input(
                "Filtrar periodo a consolidar:",
                value=(min_f, max_f),
                min_value=min_f,
                max_value=max_f,
            )
        else:
            rango_seleccionado = None

        if st.button("🚀 Procesar datos y generar reporte"):
            with st.spinner("Procesando periodo seleccionado y ejecutando control de calidad..."):

                numeric_cols = [
                    "tseca", "tmin", "tmax", "lluvia", "hum_rel", "pre_atmos",
                    "nub", "dir_viento", "vel_viento", "eva_tanque", "eva_piche",
                    "bri_solar", "rad_solar", "tsuelo_5", "tsuelo_50", "tsuelo_100"
                ]
                for col in numeric_cols:
                    df_unificado[col] = limpiar_numero_resiliente(df_unificado[col])

                # PASO 3.5: ALINEACIÓN CLIMATOLÓGICA DE LLUVIA (07:00 -> DÍA ANTERIOR)
                # Nota: Calculamos la lluvia desplazada ANTES de filtrar el rango de fechas
                # para no perder la lluvia del último día (que viene en las 07:00 del día siguiente).
                df_lluvia = df_unificado[["estacion_std", "fecha_dt", "hora_std", "lluvia"]].copy()
                df_lluvia = df_lluvia[df_lluvia["lluvia"].notnull() & df_lluvia["fecha_dt"].notnull()]
                if desplazar_lluvia_en_consolidado:
                    mask_07 = df_lluvia["hora_std"] == "07:00"
                    df_lluvia.loc[mask_07, "fecha_dt"] = (
                        df_lluvia.loc[mask_07, "fecha_dt"] - pd.Timedelta(days=1)
                    )

                lluvia_agrupada = (
                    df_lluvia.groupby(["estacion_std", "fecha_dt"])["lluvia"]
                    .sum(min_count=1)
                    .to_dict()
                )

                # Aplicar filtro de rango de fechas si el usuario seleccionó inicio y fin
                if isinstance(rango_seleccionado, tuple) and len(rango_seleccionado) == 2:
                    f_ini = pd.Timestamp(rango_seleccionado[0])
                    f_fin = pd.Timestamp(rango_seleccionado[1])
                    df_unificado = df_unificado[
                        (df_unificado["fecha_dt"] >= f_ini)
                        & (df_unificado["fecha_dt"] <= f_fin)
                    ].copy()
                    lluvia_agrupada = {
                        k: v for k, v in lluvia_agrupada.items()
                        if f_ini <= k[1] <= f_fin
                    }

                def fmt_fecha(dt):
                    return dt.strftime("%Y-%m-%d") if pd.notnull(dt) else "Fecha Nula"

                df_unificado["fecha_str"] = df_unificado["fecha_dt"].apply(fmt_fecha)

                # PASO 4: CONSOLIDACIÓN DIARIA
                registros_consolidados = []
                claves_obs = set(
                    zip(
                        df_unificado[df_unificado["fecha_dt"].notnull()]["estacion_std"],
                        df_unificado[df_unificado["fecha_dt"].notnull()]["fecha_dt"],
                    )
                )
                claves_lluvia = set(lluvia_agrupada.keys())
                todas_las_claves = sorted(
                    list(claves_obs | claves_lluvia),
                    key=lambda x: (x[0], x[1]),
                )

                grupos_dict = {
                    k: g
                    for k, g in df_unificado.groupby(["estacion_std", "fecha_dt"], dropna=False)
                    if pd.notnull(k[1])
                }

                for estacion, fecha in todas_las_claves:
                    group = grupos_dict.get(
                        (estacion, fecha), pd.DataFrame(columns=df_unificado.columns)
                    )

                    if not group.empty:
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

                        g_07 = group[group["hora_std"] == "07:00"]
                        eva_tanque_val = (
                            g_07["eva_tanque"].values[0]
                            if not g_07.empty and pd.notnull(g_07["eva_tanque"].values[0])
                            else (
                                group["eva_tanque"].dropna().iloc[0]
                                if not group["eva_tanque"].dropna().empty
                                else np.nan
                            )
                        )
                        eva_piche_val = (
                            g_07["eva_piche"].values[0]
                            if not g_07.empty and pd.notnull(g_07["eva_piche"].values[0])
                            else (
                                group["eva_piche"].dropna().iloc[0]
                                if not group["eva_piche"].dropna().empty
                                else np.nan
                            )
                        )

                        g_18 = group[group["hora_std"] == "18:00"]
                        brillo_solar_val = (
                            g_18["bri_solar"].values[0]
                            if not g_18.empty and pd.notnull(g_18["bri_solar"].values[0])
                            else group["bri_solar"].max()
                        )
                        rad_solar_val = (
                            g_18["rad_solar"].values[0]
                            if not g_18.empty and pd.notnull(g_18["rad_solar"].values[0])
                            else group["rad_solar"].max()
                        )

                        tsuelo_5_val = (
                            round(float(group["tsuelo_5"].dropna().mean()), 1)
                            if not group["tsuelo_5"].dropna().empty
                            else np.nan
                        )
                        tsuelo_50_val = (
                            round(float(group["tsuelo_50"].dropna().mean()), 1)
                            if not group["tsuelo_50"].dropna().empty
                            else np.nan
                        )
                        tsuelo_100_val = (
                            round(float(group["tsuelo_100"].dropna().mean()), 1)
                            if not group["tsuelo_100"].dropna().empty
                            else np.nan
                        )

                        fenomenos_val = parsear_fenomenos_multiselect(group["fenomenos"])

                        def get_tri_list(col_name):
                            res = []
                            for h in ["07:00", "13:00", "18:00"]:
                                vals = group[group["hora_std"] == h][col_name].values
                                res.append(vals[0] if len(vals) > 0 else np.nan)
                            return res

                        dict_derivadas = calcular_registro_unico_diario(
                            p_list=get_tri_list("pre_atmos"),
                            hr_list=get_tri_list("hum_rel"),
                            t_seca_media=tmed,
                            nub_list=get_tri_list("nub"),
                            v_dir_list=get_tri_list("dir_viento"),
                            v_vel_list=get_tri_list("vel_viento"),
                        )
                    else:
                        tmed = tmin_dia = tmax_dia = np.nan
                        eva_tanque_val = eva_piche_val = brillo_solar_val = rad_solar_val = np.nan
                        tsuelo_5_val = tsuelo_50_val = tsuelo_100_val = np.nan
                        fenomenos_val = "Ninguno"
                        dict_derivadas = {
                            "Presion_Diaria_hPa": np.nan,
                            "Humedad_Diaria_Pct": np.nan,
                            "Termometro_Humedo_Diario_C": np.nan,
                            "Nubosidad_Diaria_Cod": np.nan,
                            "Dir_Viento_Diaria_Deg": np.nan,
                        }

                    lluvia_total = lluvia_agrupada.get((estacion, fecha), np.nan)

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

                # Resumen del periodo procesado
                st.success(
                    f"✅ ¡Procesamiento completado! Se consolidaron **{len(df_consolidado)}** registros diarios "
                    f"en **{df_consolidado['Estacion'].nunique()}** estaciones."
                )

                # Generar Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_consolidado.to_excel(writer, index=False, sheet_name="Consolidado")
                excel_data = output.getvalue()

                st.download_button(
                    label="📥 Descargar Archivo Excel Consolidado Completo",
                    data=excel_data,
                    file_name="consolidacion_archivos_kobocollect.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

                # Vista previa rápida de cobertura por fecha
                with st.expander("📊 Cobertura de registros por fecha (Auditoría diaria/semanal/mensual)", expanded=False):
                    resumen_fechas = (
                        df_consolidado.groupby("Fecha")
                        .agg(
                            Estaciones=("Estacion", "nunique"),
                            Con_TMAX=("TMAX", lambda x: x.notnull().sum()),
                            Con_TMIN=("TMIN", lambda x: x.notnull().sum()),
                            Con_Lluvia=("LLUVIA_ACUM", lambda x: x.notnull().sum()),
                        )
                        .reset_index()
                    )
                    st.dataframe(resumen_fechas, use_container_width=True)

                # PASO 5: REPORTE CONTROL DE CALIDAD
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

                with st.expander(f"🌧️ Lluvias extremas (> 40 mm) ({len(ex_lluvia)} casos)", expanded=True):
                    if not ex_lluvia.empty:
                        st.dataframe(ex_lluvia[["estacion_std", "fecha_str", "hora_std", "lluvia"]], use_container_width=True)
                    else:
                        st.success("No hay registros de lluvia extrema.")

                with st.expander(f"🔥 Temperaturas máximas extremas (> 42 °C) ({len(ex_tmax)} casos)", expanded=True):
                    if not ex_tmax.empty:
                        st.dataframe(ex_tmax[["estacion_std", "fecha_str", "hora_std", "tmax"]], use_container_width=True)
                    else:
                        st.success("No hay registros de temperaturas máximas extremas.")

                with st.expander(f"❄️ Temperaturas mínimas extremas (< 0 °C) ({len(ex_tmin)} casos)", expanded=True):
                    if not ex_tmin.empty:
                        st.dataframe(ex_tmin[["estacion_std", "fecha_str", "hora_std", "tmin"]], use_container_width=True)
                    else:
                        st.success("No hay registros de temperaturas mínimas bajo el punto de congelación.")

    else:
        st.info("Por favor asegúrate de subir los tres archivos descargados de Kobo (Automáticas, Climáticas y Sinópticas) en el menú lateral.")
else:
    st.info("👈 Comienza subiendo tus archivos CSV en el panel lateral para habilitar la auditoría y descarga.")
