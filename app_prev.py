import ast
import folium
import geopandas as gpd
import pandas as pd
import plotly.express as px
import shapely.wkb
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("Road Geometry & Posterior Sample Inspector")


@st.cache_data
def load_and_prep_data(csv_path):
  # Read CSV and drop identical duplicate rows per road
  df = pd.read_csv(csv_path).drop_duplicates(subset=["road_id"]).reset_index()

  # Convert WKB hex geometry string to Shapely geometry
  df["geometry"] = df["geom"].apply(
      lambda x: shapely.wkb.loads(bytes.fromhex(x))
  )

  # Convert from Ordnance Survey National Grid (EPSG:27700) to WGS84 (EPSG:4326)
  gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:27700").to_crs(
      epsg=4326
  )
  return gdf


gdf = load_and_prep_data("time_testing_results_clean_withgeom.csv")

# Create layout columns
col1, col2 = st.columns([1, 1])

with col1:
  st.subheader("Interactive Map")
  # Center map based on dataset bounds
  center_lat = gdf.geometry.centroid.y.mean()
  center_lon = gdf.geometry.centroid.x.mean()
  m = folium.Map(location=[center_lat, center_lon], zoom_start=13)

  # Render roads on map
  folium.GeoJson(
      gdf,
      name="Roads",
      tooltip=folium.GeoJsonTooltip(
          fields=["road_id", "actual_crime_freq"],
          aliases=["Road ID:", "Crime Freq:"],
      ),
      style_function=lambda x: {
          "color": "#1f77b4",
          "weight": 4,
          "opacity": 0.8,
      },
  ).add_to(m)

  map_output = st_folium(m, width=600, height=500)

with col2:
  st.subheader("Observation Samples Histogram")

  selected_road_id = None
  if map_output and map_output.get("last_active_drawing"):
    props = map_output["last_active_drawing"].get("properties")
    if props:
      selected_road_id = props.get("road_id")

  if selected_road_id is not None:
    road_row = gdf[gdf["road_id"] == selected_road_id].iloc[0]

    # Convert string representation of list to actual Python list
    obs_samples = ast.literal_eval(road_row["obs_samples"])

    fig = px.histogram(
        x=obs_samples,
        nbins=30,
        title=f"obs_samples Distribution for Road ID: {selected_road_id}",
        labels={"x": "obs_samples Value", "count": "Frequency"},
        color_discrete_sequence=["#2ca02c"],
    )
    st.plotly_chart(fig, use_container_width=True)
  else:
    st.info("Click on any road line on the map to display its histogram.")
