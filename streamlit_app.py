import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium, folium_static
from shapely.geometry import Point
from geopy.distance import geodesic
from streamlit_geolocation import streamlit_geolocation
import hashlib
from io import BytesIO
import simplekml
from folium.plugins import MarkerCluster

st.set_page_config(page_title="Mapa Interativo e Field Tools", layout="wide")

st.title("🗺️ Sistema Integrado de Mapas")

tab1, tab2 = st.tabs(["🗺️ Zonas e Distritos", "📍 Pesquisa de Sites"])

# === ABA 1: Mapa por Zonas ===
with tab1:
    try:
        gdf = gpd.read_file("data/distritos.shp")

        zonas_personalizadas = {
            'Porto': ['Aveiro', 'Porto', 'Braga', 'Viana do Castelo'],
            'Lamego': ['Vila Real', 'Bragança', 'Viseu', 'Lamego', 'Guarda'],
            'Castelo Branco': ['Castelo Branco', 'Portalegre'],
            'Santarém': ['Santarém', 'Leiria', 'Coimbra'],
            'Lisboa': ['Lisboa'],
            'Setúbal': ['Setúbal', 'Évora'],
            'Faro': ['Faro', 'Beja'],
            'Ilhas - Madeira': ['Madeira'],
            'Ilhas - Açores': ['Açores']
        }

        def obter_zona(distrito):
            for zona, distritos in zonas_personalizadas.items():
                if distrito in distritos:
                    return zona
            return 'Desconhecida'

        col_distrito = 'NAME_1'
        gdf['zona'] = gdf[col_distrito].apply(obter_zona)

        zonas_opcoes = sorted(gdf['zona'].unique())
        distritos_opcoes = sorted(gdf[col_distrito].unique())

        col1, col2 = st.columns(2)
        zona_sel = col1.selectbox("Filtrar por zona:", ["Todas"] + zonas_opcoes)
        distrito_sel = col2.selectbox("Filtrar por distrito:", ["Todos"] + distritos_opcoes)

        gdf_filtrado = gdf.copy()
        if zona_sel != "Todas":
            gdf_filtrado = gdf_filtrado[gdf_filtrado['zona'] == zona_sel]
        if distrito_sel != "Todos":
            gdf_filtrado = gdf_filtrado[gdf_filtrado[col_distrito] == distrito_sel]

        def gerar_cor_estavel(nome):
            hash_val = int(hashlib.md5(nome.encode()).hexdigest(), 16)
            return f"#{hash_val % 0xFFFFFF:06x}"

        gdf_filtrado['cor'] = gdf_filtrado[col_distrito].apply(gerar_cor_estavel)

        m = folium.Map(location=[39.5, -8.0], zoom_start=7)

        folium.GeoJson(
            gdf_filtrado,
            style_function=lambda feature: {
                'fillColor': feature['properties']['cor'],
                'color': 'black',
                'weight': 1,
                'fillOpacity': 0.6,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=[col_distrito, 'zona'],
                aliases=["Distrito", "Zona"],
                sticky=True
            )
        ).add_to(m)

        uploaded_sites = st.file_uploader("📁 Carregar base de sites para visualizar (opcional)", type=["xlsx"], key="zona_sites")
        if uploaded_sites:
            df_sites = pd.read_excel(uploaded_sites)
            df_sites = df_sites.dropna(subset=["Latitudine", "Longitudine", "Cod Site"])
            df_sites["Cod Site"] = df_sites["Cod Site"].astype(str).str.strip().str.upper()

            gdf_sites = gpd.GeoDataFrame(
                df_sites,
                geometry=[Point(lon, lat) for lat, lon in zip(df_sites["Latitudine"], df_sites["Longitudine"])],
                crs="EPSG:4326"
            )
            gdf_sites = gpd.sjoin(gdf_sites, gdf[[col_distrito, "zona", "geometry"]], how="left", predicate="intersects")

            if zona_sel != "Todas":
                gdf_sites = gdf_sites[gdf_sites['zona'] == zona_sel]
            if distrito_sel != "Todos":
                gdf_sites = gdf_sites[gdf_sites[col_distrito] == distrito_sel]

            show_sites = st.checkbox("👁️ Mostrar sites no mapa", value=True)

            if show_sites:
                cluster = MarkerCluster().add_to(m)

                for _, row in gdf_sites.iterrows():
                    lat, lon, cod = row["Latitudine"], row["Longitudine"], row["Cod Site"]
                    google_maps_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
                    waze_url = f"https://waze.com/ul?ll={lat},{lon}&navigate=yes"

                    folium.CircleMarker([lat, lon], radius=5, color="red", fill=True, fill_opacity=1.0).add_to(cluster)
                    folium.Marker(
                        [lat, lon],
                        icon=folium.DivIcon(html=f"<div style='font-size:12px; color:black; font-weight:bold;'>{cod}</div>"),
                        popup=folium.Popup(
                            f"<b>{cod}</b><br>"
                            f"<a href='{google_maps_url}' target='_blank'>Google Maps</a><br>"
                            f"<a href='{waze_url}' target='_blank'>Waze</a>", max_width=250
                        )
                    ).add_to(cluster)

            st.markdown("### 📍 Sites localizados na zona/distrito")
            st.dataframe(gdf_sites[["Cod Site", "Latitudine", "Longitudine", col_distrito, "zona"]])

            # Exportar Excel
            output_excel = BytesIO()
            gdf_sites.drop(columns="geometry").to_excel(output_excel, index=False, engine='openpyxl')
            st.download_button(
                label="⬇️ Descarregar Excel dos Sites",
                data=output_excel.getvalue(),
                file_name="sites_filtrados.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            # Exportar KMZ
            kml = simplekml.Kml()
            for _, row in gdf_sites.iterrows():
                kml.newpoint(name=row["Cod Site"], coords=[(row["Longitudine"], row["Latitudine"])])
            kmz_bytes = BytesIO()
            kml.savekmz(kmz_bytes)
            st.download_button(
                label="⬇️ Descarregar KMZ dos Sites",
                data=kmz_bytes.getvalue(),
                file_name="sites_filtrados.kmz",
                mime="application/vnd.google-earth.kmz"
            )

        st.subheader("🌍 Mapa ")
        st_folium(m, use_container_width=True, height=600)

    except Exception as e:
        st.error(f"Erro ao carregar dados de distritos: {e}")
