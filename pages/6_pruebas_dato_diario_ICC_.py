import io
import json
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
from shapely.geometry import MultiPoint, shape, mapping

st.set_page_config(page_title="Generador de Isotermas TMIN - uMap", page_icon="❄️", layout="wide")
st.title("❄️ Generador de Mapas de Temperaturas Mínimas (uMap GeoJSON)")
st.markdown(
    "Cruza `datos-diarios_prelim_temp-celci.xlsx` con `metadata.csv` para generar "
    "capas GeoJSON de **estaciones** e **isotermas de frío** listas para publicar en uMap."
)

col1, col2 = st.sidebar.columns(1), st.sidebar.columns(1)
file_temp = st.sidebar.file_uploader("1. Sube datos-diarios_prelim_temp-celci.xlsx", type=["xlsx", "xls"])
file_meta = st.sidebar.file_uploader("2. Sube metadata.csv", type=["csv"])

if file_temp and file_meta:
    df_temp = pd.read_excel(file_temp)
    meta = pd.read_csv(file_meta)
    meta["Código"] = meta["Código"].astype(str).str.strip()

    df_temp["FECHA_STR"] = pd.to_datetime(df_temp["FECHA"], errors="coerce").dt.strftime("%Y-%m-%d")
    fechas_disp = sorted(df_temp["FECHA_STR"].dropna().unique(), reverse=True)

    fecha_sel = st.sidebar.selectbox("3. Selecciona la fecha a mapear:", fechas_disp)
    variable_sel = st.sidebar.selectbox("4. Variable térmica:", ["TMIN", "TMAX", "TMED"], index=0)

    if st.button("🗺️ Generar Capas GeoJSON para uMap"):
        sub = df_temp[(df_temp["FECHA_STR"] == fecha_sel) & (df_temp["VARIABLE"] == variable_sel)]
        if sub.empty:
            st.warning("No hay registros para esa fecha y variable.")
        else:
            row = sub.iloc[0]
            registros = []
            for code in df_temp.columns[2:]:
                if code == "FECHA_STR":
                    continue
                val = pd.to_numeric(row[code], errors="coerce")
                if pd.notnull(val):
                    registros.append({"Código": str(code).strip(), "Valor": round(float(val), 1)})

            df_merged = pd.merge(pd.DataFrame(registros), meta, on="Código", how="inner")
            st.success(f"✅ {len(df_merged)} estaciones geolocalizadas para **{variable_sel}** ({fecha_sel}).")

            # 1. GeoJSON de Puntos (Estaciones)
            features_pts = []
            for _, r in df_merged.iterrows():
                features_pts.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [float(r["Longitud"]), float(r["Latitud"])]},
                    "properties": {
                        "Codigo": r["Código"],
                        "Estacion": r["Estación"],
                        "Departamento": r["Departamento"],
                        "Municipio": r["Municipio"],
                        "Altitud_msnm": int(r["Altitud"]) if pd.notnull(r["Altitud"]) else None,
                        "Temperatura_C": float(r["Valor"]),
                        "Variable": variable_sel,
                        "Fecha": fecha_sel,
                    },
                })
            gj_pts_str = json.dumps({"type": "FeatureCollection", "features": features_pts}, ensure_ascii=False, indent=2)

            # 2. GeoJSON de Polígonos (Isotermas interpoladas)
            lons = df_merged["Longitud"].values
            lats = df_merged["Latitud"].values
            vals = df_merged["Valor"].values

            grid_lon = np.linspace(-92.3, -88.2, 220)
            grid_lat = np.linspace(13.7, 17.9, 220)
            XI, YI = np.meshgrid(grid_lon, grid_lat)

            ZI_lin = griddata((lons, lats), vals, (XI, YI), method="linear")
            ZI_near = griddata((lons, lats), vals, (XI, YI), method="nearest")
            ZI_smooth = gaussian_filter(np.where(np.isnan(ZI_lin), ZI_near, ZI_lin), sigma=2.2)

            levels = [0, 4, 8, 12, 16, 20, 24, 32, 42]
            colors_hex = ["#313695", "#4575b4", "#74add1", "#abd9e9", "#fee090", "#fdae61", "#f46d43", "#d73027"]
            labels_rango = [
                "0 a 4 °C (Riesgo de helada)",
                "4 a 8 °C (Muy frío)",
                "8 a 12 °C (Frío)",
                "12 a 16 °C (Fresco)",
                "16 a 20 °C (Templado)",
                "20 a 24 °C (Cálido)",
                "24 a 32 °C (Caluroso)",
                "Mayor a 32 °C (Muy caluroso)",
            ]

            fig, ax = plt.subplots()
            cs = ax.contourf(XI, YI, ZI_smooth, levels=levels)
            plt.close(fig)

            # Envolvente territorial de estaciones
            pts_env = MultiPoint(list(zip(meta["Longitud"], meta["Latitud"]))).convex_hull.buffer(0.28)

            features_poly = []
            for idx, segs in enumerate(cs.allsegs):
                for poly_coords in segs:
                    if len(poly_coords) < 4:
                        continue
                    ring = [[round(float(pt[0]), 5), round(float(pt[1]), 5)] for pt in poly_coords]
                    if ring[0] != ring[-1]:
                        ring.append(ring[0])
                    geom = shape({"type": "Polygon", "coordinates": [ring]})
                    if not geom.is_valid:
                        geom = geom.buffer(0)
                    inter = geom.intersection(pts_env)
                    if not inter.is_empty:
                        features_poly.append({
                            "type": "Feature",
                            "geometry": mapping(inter),
                            "properties": {
                                "Rango_Temperatura": labels_rango[idx],
                                "Variable": variable_sel,
                                "Fecha": fecha_sel,
                                "_umap_options": {
                                    "fillColor": colors_hex[idx],
                                    "color": colors_hex[idx],
                                    "weight": 1,
                                    "fillOpacity": 0.55,
                                },
                            },
                        })

            gj_poly_str = json.dumps({"type": "FeatureCollection", "features": features_poly}, ensure_ascii=False)

            st.subheader("🏆 Top 5 Estaciones más frías del día")
            st.dataframe(
                df_merged[["Código", "Estación", "Departamento", "Municipio", "Altitud", "Valor"]]
                .sort_values("Valor")
                .head(5),
                use_container_width=True,
            )

            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    label=f"📍 Descargar Estaciones ({variable_sel}_{fecha_sel}.geojson)",
                    data=gj_pts_str.encode("utf-8"),
                    file_name=f"estaciones_{variable_sel.lower()}_{fecha_sel}.geojson",
                    mime="application/geo+json",
                    use_container_width=True,
                )
            with c2:
                st.download_button(
                    label=f"🗺️ Descargar Isotermas ({variable_sel}_{fecha_sel}.geojson)",
                    data=gj_poly_str.encode("utf-8"),
                    file_name=f"isotermas_{variable_sel.lower()}_{fecha_sel}.geojson",
                    mime="application/geo+json",
                    use_container_width=True,
                )
else:
    st.info("👈 Sube el Excel de temperaturas y `metadata.csv` en el panel lateral.")
