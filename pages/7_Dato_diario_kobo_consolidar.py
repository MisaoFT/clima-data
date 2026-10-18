import io
import numpy as np
import pandas as pd
import streamlit as st

# Configuración de la página
st.set_page_config(
    page_title="Control de Calidad y Consolidado Kobo",
    page_icon="🌤️",
    layout="wide",
)

st.title("🌤️ Auditoría de Calidad y Consolidación Meteorológica")
st.markdown(
    "Sube tus archivos de KoboToolbox para visualizar las alertas de"
    " temperatura y lluvia, y descarga el archivo consolidado."
)

# Panel lateral
st.sidebar.header("📁 Carga de Archivos CSV")
uploaded_files = st.sidebar.file_uploader(
    "Selecciona tus archivos de Kobo",
    type=["csv"],
    accept_multiple_files=True,
)

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
  st.sidebar.write(
      f"- **Climáticas:** {file_clim.name if file_clim else '❌'}"
  )
  st.sidebar.write(f"- **Sinópticas:** {file_sino.name if file_sino else '❌'}")

  if file_auto and file_clim and file_sino:
    if st.button("🚀 Procesar Datos y Generar Reporte"):
      with st.spinner("Procesando archivos y ejecutando control de calidad..."):

        # ==========================================
        # FUNCIÓN DE LECTURA Y RESCATE DE FECHA
        # ==========================================
        def cargar_y_extraer_fecha(file_bytes):
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

        # Carga de datos
        df_auto = cargar_y_extraer_fecha(file_auto.getvalue())
        df_auto = df_auto[[
            "Nombre de la estación",
            "Fecha",
            "fecha_start_clean",
            "Hora",
            "Lluvia total:",
        ]].copy()
        df_auto.columns = ["estacion", "fecha_manual", "fecha_start", "hora", "lluvia"]
        df_auto["tseca"] = np.nan
        df_auto["tmin"] = np.nan
        df_auto["tmax"] = np.nan

        df_clim = cargar_y_extraer_fecha(file_clim.getvalue())
        df_clim = df_clim[[
            "Nombre de la Estacion:",
            "Fecha",
            "fecha_start_clean",
            "Hora",
            "Temperatura Seca:",
            "Temperatura minima:",
            "Temperatura maxima:",
            "Lluvia total:",
        ]].copy()
        df_clim.columns = [
            "estacion",
            "fecha_manual",
            "fecha_start",
            "hora",
            "tseca",
            "tmin",
            "tmax",
            "lluvia",
        ]

        df_sino = cargar_y_extraer_fecha(file_sino.getvalue())
        df_sino = df_sino[[
            "estacion",
            "Fecha",
            "fecha_start_clean",
            "Hora",
            "tseca",
            "tmin",
            "tmax",
            "lluvia",
        ]].copy()
        df_sino.columns = [
            "estacion",
            "fecha_manual",
            "fecha_start",
            "hora",
            "tseca",
            "tmin",
            "tmax",
            "lluvia",
        ]

        df_unificado = pd.concat([df_auto, df_clim, df_sino], ignore_index=True)

        # ==========================================
        # HOMOLOGACIÓN Y JERARQUÍA DE FECHAS
        # ==========================================
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

        for col in ["tseca", "tmin", "tmax", "lluvia"]:
          df_unificado[col] = pd.to_numeric(
              df_unificado[col], errors="coerce"
          )

        def fmt_fecha(dt):
          return dt.strftime("%Y-%m-%d") if pd.notnull(dt) else "Fecha Nula"

        df_unificado["fecha_str"] = df_unificado["fecha_dt"].apply(fmt_fecha)

        # ==========================================
        # CONSOLIDACIÓN FINAL (PARA DESCARGA)
        # ==========================================
        registros_consolidados = []
        grupos = df_unificado.groupby(["estacion_std", "fecha_dt"], dropna=False)

        for (estacion, fecha), group in grupos:
          t_07 = group[group["hora_std"] == "07:00"]["tseca"].values
          t_13 = group[group["hora_std"] == "13:00"]["tseca"].values
          t_18 = group[group["hora_std"] == "18:00"]["tseca"].values

          val_07 = (
              t_07[0] if len(t_07) > 0 and pd.notnull(t_07[0]) else None
          )
          val_13 = (
              t_13[0] if len(t_13) > 0 and pd.notnull(t_13[0]) else None
          )
          val_18 = (
              t_18[0] if len(t_18) > 0 and pd.notnull(t_18[0]) else None
          )

          if (
              val_07 is not None
              and val_13 is not None
              and val_18 is not None
          ):
            tmed = round((val_07 + val_13 + val_18) / 3.0, 1)
          else:
            tmed = np.nan

          tmin_dia = group["tmin"].min()
          tmax_dia = group["tmax"].max()
          lluvia_total = group["lluvia"].sum(min_count=1)

          registros_consolidados.append({
              "Estacion": estacion,
              "Fecha": fmt_fecha(fecha),
              "TMED": tmed,
              "TMIN": tmin_dia if pd.notnull(tmin_dia) else np.nan,
              "TMAX": tmax_dia if pd.notnull(tmax_dia) else np.nan,
              "LLUVIA_ACUM": (
                  lluvia_total if pd.notnull(lluvia_total) else np.nan
              ),
          })

        df_consolidado = pd.DataFrame(registros_consolidados)

        # Generar Excel en memoria para descarga inmediata
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
          df_consolidado.to_excel(writer, index=False, sheet_name="Consolidado")
        excel_data = output.getvalue()

        # Botón de descarga principal bien visible arriba
        st.success("✅ ¡Procesamiento completado con éxito!")
        st.download_button(
            label="📥 Descargar Archivo Excel Consolidado",
            data=excel_data,
            file_name="consolidado_kobo_valido.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            use_container_width=True,
        )

        # ==========================================
        # REPORTE DE ALERTAS Y ANOMALÍAS
        # ==========================================
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

        with st.expander(
            f"⚠️ Inconsistencias Físicas: Tmin >= Tseca ({len(inc_tmin)} casos)",
            expanded=True,
        ):
          if not inc_tmin.empty:
            st.dataframe(
                inc_tmin[[
                    "estacion_std",
                    "fecha_str",
                    "hora_std",
                    "tmin",
                    "tseca",
                ]],
                use_container_width=True,
            )
          else:
            st.success("No hay registros con Tmin mayor o igual a Tseca.")

        with st.expander(
            f"⚠️ Inconsistencias Físicas: Tmax <= Tseca ({len(inc_tmax)} casos)",
            expanded=True,
        ):
          if not inc_tmax.empty:
            st.dataframe(
                inc_tmax[[
                    "estacion_std",
                    "fecha_str",
                    "hora_std",
                    "tmax",
                    "tseca",
                ]],
                use_container_width=True,
            )
          else:
            st.success("No hay registros con Tmax menor o igual a Tseca.")

        with st.expander(
            f"🌧️ Lluvias Extremas (> 40 mm) ({len(ex_lluvia)} casos)",
            expanded=True,
        ):
          if not ex_lluvia.empty:
            st.dataframe(
                ex_lluvia[["estacion_std", "fecha_str", "hora_std", "lluvia"]],
                use_container_width=True,
            )
          else:
            st.success("No hay registros de lluvia extrema.")

        with st.expander(
            f"🔥 Temperaturas Máximas Extremas (> 42 °C) ({len(ex_tmax)} casos)",
            expanded=True,
        ):
          if not ex_tmax.empty:
            st.dataframe(
                ex_tmax[["estacion_std", "fecha_str", "hora_std", "tmax"]],
                use_container_width=True,
            )
          else:
            st.success("No hay registros de temperaturas máximas extremas.")

        with st.expander(
            f"❄️ Temperaturas Mínimas Extremas (< 0 °C) ({len(ex_tmin)} casos)",
            expanded=True,
        ):
          if not ex_tmin.empty:
            st.dataframe(
                ex_tmin[["estacion_std", "fecha_str", "hora_std", "tmin"]],
                use_container_width=True,
            )
          else:
            st.success(
                "No hay registros de temperaturas mínimas bajo el punto de"
                " congelación."
            )

  else:
    st.info(
        "Por favor asegúrate de subir los tres archivos (Automáticas,"
        " Climáticas y Sinópticas) en el menú lateral."
    )
else:
  st.info(
      "👈 Comienza subiendo tus archivos CSV en el panel lateral para"
      " habilitar la auditoría y descarga."
  )
