import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import geopandas as gpd
import contextily as cx
from scipy.interpolate import Rbf
import io
from io import BytesIO

st.set_page_config(layout="wide")
st.title("🌧️ Generador de mapa preliminar de lluvias parciales (Isoyetas)")
st.write("Sube el archivo de salida de datos diarios para generar la composición espacial interpolada.")

# =====================================================================
# 1. METADATA FIJA DE LAS 93 ESTACIONES (ICC + INSIVUMEH)
# =====================================================================
METADATA_ESTACIONES = {
    'Código': ['ICC041101AT', 'ICC041201AT', 'ICC050101AT', 'ICC050201AT', 'ICC050202AT', 'ICC050203AT', 'ICC050301AT', 'ICC050302AT', 'ICC050501AT', 'ICC050502AT', 'ICC050601AT', 'ICC050602AT', 'ICC050701AT', 'ICC050901AT', 'ICC051301AT', 'ICC051401AT', 'ICC060801AT', 'ICC060901AT', 'ICC060902AT', 'ICC100601AT', 'ICC100701AT', 'ICC101001AT', 'ICC101401AT', 'ICC110101AT', 'ICC110102AT', 'ICC110601AT', 'ICC110701AT', 'ICC121701AT', 'ICC221501AT', 'INS010101CV', 'INS010102CV', 'INS010301AT', 'INS010701CV', 'INS010801AT', 'INS011401AT', 'INS020301CV', 'INS020302CV', 'INS030101AT', 'INS030801CV', 'INS040101CV', 'INS040301CV', 'INS040801AT', 'INS041001CV', 'INS050101AT', 'INS050101CV', 'INS050901CV', 'INS060101CV', 'INS070101CV', 'INS071301CV', 'INS071901CV', 'INS080101AT', 'INS090101CV', 'INS090301CV', 'INS090401AT', 'INS100101CV', 'INS110101CV', 'INS110701CV', 'INS120101CV', 'INS121601CV', 'INS121701CV', 'INS122101AT', 'INS122301AT', 'INS130101CV', 'INS130601CV', 'INS131501CV', 'INS140101AT', 'INS140301CV', 'INS141301CV', 'INS141601CV', 'INS141901CV', 'INS142201AT', 'INS150401CV', 'INS150701CV', 'INS160101CV', 'INS160701CV', 'INS161201CV', 'INS170101CV', 'INS171201CV', 'INS180101CV', 'INS180201CV', 'INS180401AT', 'INS180501AT', 'INS190201CV', 'INS190301CV', 'INS190901CV', 'INS200501CV', 'INS200701CV', 'INS210101AT', 'INS210101CV', 'INS210601CV', 'INS220501CV', 'INS221401CV', 'INS221701CV'],
    'Estación': ['El Platanar', 'Yepocapa (FCA-CATIE)', 'Concepción', 'Tehuantepeq', 'Cengicaña', 'El Bálsamo', 'Bouganvilia', 'Costa Brava', 'Amazonas', 'Trinidad', 'Irlanda', 'Petén Oficina', 'Bonanza', 'La Giralda', 'Puyumate', 'San Antonio EV', 'La Maquina', 'La Candelaria', 'San Rafael', 'Naranjales', 'San Nicolás', 'Lorena', 'Cocales', 'Chiquirines', 'Xoluta', 'Tululá', 'Providencia', 'Alamo', 'Trinidad Magdalena', 'INSIVUMEH', 'La Aurora', 'San José Pinula', 'San Pedro Ayampuc', 'Lo de Coy', 'Amatitlán', 'Los Albores', 'San Agustín Acasaguastlán', 'Antigua Guatemala', 'Suiza Contenta', 'Alameda Icta', 'San Martín Jilotepeque', 'Santa Margarita', 'Santa Cruz Balanyá', 'Concepción', 'Sabana Grande', 'San José Aeropuerto', 'Los Esclavos', 'El Tablón', 'El Capitán', 'Santiago Atitlán', 'Totonicapán', 'Los Altos', 'Labor Ovalle', 'Pachuté', 'Mazatenango', 'Retalhuleu Aeropuerto', 'Champerico Fegua', 'San Marcos PHC', 'Catarina', 'Tecún Umán Fegua Ayutla', 'La Reforma', 'Ixchiguán', 'Huehuetenango', 'San Pedro Necta', 'Todos Santos', 'Santa Cruz Quiché', 'Chinique', 'Nebaj', 'Sacapulas', 'Chixoy PCH', 'Playa Grande Met (Ixcan)', 'Cubulco', 'San Jerónimo R.H.', 'Cobán', 'Panzos PHC Altaverapaz', 'Santa María Cahabón', 'Flores Aeropuerto', 'Poptún', 'Puerto Barrios PHC', 'Las Vegas PHC', 'Morales Met', 'Mariscos', 'La Fragua', 'Pasabien', 'La Unión', 'Camotán', 'Esquipulas', 'Jalapa', 'Potrero Carrillo', 'La Ceibita', 'Asunción Mita R.H.', 'Montufar', 'Quezada'],
    'Latitud': [14.559675, 14.483053, 14.337389, 14.167056, 14.329931, 14.280378, 14.11999444, 14.243342, 14.066847, 14.153794, 14.145975, 14.258658, 14.078331, 13.980289, 14.261556, 13.995419, 13.8986833, 13.912322, 14.02443611, 14.3650083, 14.184561, 14.520292, 14.382847, 14.5594444, 14.477133, 14.508158, 14.365786, 14.6281861, 13.93205, 14.587267, 14.58619, 14.52392, 14.7834166, 14.62109, 14.46785, 15.0525, 14.9502817, 14.53974, 14.618572, 14.637936, 14.777474, 14.50575, 14.683227, 14.32352, 14.373773, 13.936665, 14.2528, 14.7902778, 14.644497, 14.630858, 14.91082, 14.8599015, 14.871334, 14.98341, 14.5283333, 14.52486, 14.29397, 14.96715, 14.856361, 14.70195, 14.8, 15.16483, 15.31828, 15.49459, 15.5080222, 15.05016, 15.04675, 15.399247, 15.290621, 15.357893, 15.98888, 15.109023, 15.060903, 15.46992, 15.3974, 15.608429, 16.916093, 16.32566, 15.730161, 15.585416, 15.478211, 15.42866, 14.96553, 15.030222, 14.9633333, 14.821751, 14.559694, 14.59639, 14.74996, 14.494509, 14.335447, 13.80853, 14.232852],
    'Longitud': [-90.937931, -90.961541, -90.787125, -91.103564, -91.05425, -91.0031, -90.9414, -90.923006, -90.774593, -90.843911, -91.426786, -91.412297, -91.187261, -90.930753, -91.260733, -91.200217, -90.331502777778, -90.559381, -90.63366111, -91.477519, -91.603569, -91.418736, -91.196198, -92.0422222, -91.863067, -91.586808, -91.845667, -92.1377472, -90.258211, -90.532679, -90.52773, -90.39191, -90.4500096, -90.59922, -90.63039, -89.949167, -89.9738746, -90.7383, -90.659128, -90.803967, -90.792558, -91.01144, -90.918504, -90.78758, -90.830533, -90.835264, -90.2783, -91.1819444, -91.140524, -91.232526, -91.36441, -91.50807279, -91.514438, -91.57365, -91.5027778, -91.69407, -91.91426, -91.82333, -92.074858, -92.128059, -91.8167, -91.9395, -91.502403, -91.76244, -91.6003111, -91.15395, -91.019608, -91.142084, -91.091976, -90.661261, -90.74017, -90.620582, -90.252213, -90.405518, -89.64397, -89.81227, -89.86686, -89.41043, -88.584395, -88.944686, -88.823711, -89.07781, -89.58437, -89.67925, -89.2911111, -89.374614, -89.341459, -89.96739, -89.933667, -89.878944, -89.705892, -90.15446, -90.036177]}

df_meta = pd.DataFrame(METADATA_ESTACIONES)
df_meta['Código'] = df_meta['Código'].str.strip()

archivo_subido = st.file_uploader("Sube tu archivo de datos de lluvia (.xlsx o .csv)", type=['xlsx', 'csv'])

if archivo_subido is not None:
    try:
        if archivo_subido.name.endswith('.xlsx'):
            df_datos = pd.read_excel(archivo_subido, sheet_name=0)
        else:
            df_datos = pd.read_csv(archivo_subido)                    
            
        st.success(f"Archivo '{archivo_subido.name}' cargado con éxito.")                
        df_datos = df_datos[df_datos['VARIABLE'].str.contains('PREP|LLUVIA|Precipitación', case=False, na=False)]
        df_long = df_datos.melt(id_vars=['FECHA', 'VARIABLE'], var_name='Código', value_name='Lluvia_Diaria')
        df_long['Lluvia_Diaria'] = pd.to_numeric(df_long['Lluvia_Diaria'], errors='coerce')
        df_acumulada = df_long.groupby('Código')['Lluvia_Diaria'].sum(min_count=1).reset_index()
        df_acumulada.columns = ['Código', 'Lluvia_Acumulada_mm']
        df_acumulada['Código'] = df_acumulada['Código'].str.strip()                
        df_mapa = pd.merge(df_meta, df_acumulada, on='Código', how='inner')
        df_mapa = df_mapa.dropna(subset=['Latitud', 'Longitud', 'Lluvia_Acumulada_mm'])                
        
        st.info(f"📊 Estaciones validadas para interpolación: {len(df_mapa)}")
        st.subheader("🗺️ Mapa de distribución espacial de la precipitación")                
        
        gdf = gpd.GeoDataFrame(df_mapa, geometry=gpd.points_from_xy(df_mapa.Longitud, df_mapa.Latitud), crs="EPSG:4326").to_crs(epsg=3857)
        z = gdf['Lluvia_Acumulada_mm'].values                
        limites_fijos = gpd.GeoSeries(gpd.points_from_xy([-92.3, -88.1], [13.6, 17.9]), crs="EPSG:4326").to_crs(epsg=3857)
        x_min, x_max = limites_fijos.geometry.x.iloc[0], limites_fijos.geometry.x.iloc[1]
        y_min, y_max = limites_fijos.geometry.y.iloc[0], limites_fijos.geometry.y.iloc[1]
        
        xi, yi = np.meshgrid(np.linspace(x_min, x_max, 250), np.linspace(y_min, y_max, 250))
        rbf = Rbf(gdf.geometry.x.values, gdf.geometry.y.values, z, function='linear')
        zi = rbf(xi, yi)
        zi = np.clip(zi, 0, None)
        
                
        # Generación del gráfico con DPI optimizado (150)
        fig, ax = plt.subplots(figsize=(8, 8), dpi=300)
        max_lluvia = max(z.max(), 40)
        niveles = np.linspace(0,max_lluvia,12)
        contour = ax.contourf(xi, yi, zi, levels=niveles, cmap='YlGnBu', alpha=0.65)
        cx.add_basemap(ax, source=cx.providers.OpenStreetMap.Mapnik, zorder=0)
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
        ax.axis('off')
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        cbar = fig.colorbar(contour, ax=ax, orientation='horizontal', pad=0.03, shrink=0.7)
        cbar.set_label('Precipitación estimada a superficie continua (mm)', fontsize=10, weight='bold')
        ax.set_title("Mapa de precipitación acumulada de 6 horas(mm)", fontsize=13, weight='bold', pad=12)
        ax.text(0.02, -0.02, "Mapa preliminar generado automaticamente por la Sección de Climatología - INSIVUMEH-", transform=ax.transAxes, fontsize=7, fontstyle='italic', color='gray', ha='left', va='top', zorder=10)
        
     
        # --- RANKING (A la par) ---
        col_mapa, col_lista = st.columns([3, 1])
        with col_mapa:
            st.pyplot(fig, use_container_width=True)
            st.caption("Mapa preliminar con data de lluvias parciales")
        with col_lista:
            st.markdown("### 🏆 Estaciones con mayor precipitación")
            with st.container(height=600):
                st.dataframe(
                    df_mapa.sort_values(by='Lluvia_Acumulada_mm', ascending=False).head(15)[['Estación', 'Lluvia_Acumulada_mm']], 
                    hide_index=True, 
                    use_container_width=True
            )
            
        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches='tight', dpi=300)
        st.download_button("💾 Descargar mapa (PNG)", data=buf.getvalue(), file_name="mapa_lluvia_parcial.png", mime="image/png")
        
    except Exception as e:
        st.error(f"Error: {e}")