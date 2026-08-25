import folium
import geopandas as gpd
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("Road Geometry & Crime Data Inspector")


# ----------------------------------------------------
# 1. 데이터 로드 및 전처리 (Min-Max Normalization 포함)
# ----------------------------------------------------
@st.cache_data
def load_and_prep_geojson(geojson_path):
  # GeoJSON 파일 읽기
  gdf = gpd.read_file(geojson_path)

  # 속성 필드명 표준화 (컬럼명이 불일치할 경우 변경)
  rename_dict = {
      "maxspeed": "max_speed",
      "imd_deci": "imd_decile",
      "cri_deci": "cri_decile",
  }
  gdf = gdf.rename(columns={k: v for k, v in rename_dict.items() if k in gdf})

  # crime_count 컬럼이 없을 경우 pred_crime 또는 total_crime을 활용
  if "crime_count" not in gdf.columns:
    if "pred_crime" in gdf.columns:
      gdf["crime_count"] = gdf["pred_crime"]
    elif "total_crime" in gdf.columns:
      gdf["crime_count"] = gdf["total_crime"]
    else:
      gdf["crime_count"] = 0.0

  # 수치형 컬럼 변환
  numeric_cols = [
      "max_speed",
      "imd_decile",
      "build_count",
      "cri_decile",
      "crime_count",
  ]
  for col in numeric_cols:
    if col in gdf.columns:
      gdf[col] = pd.to_numeric(gdf[col], errors="coerce").fillna(0)

  # Min-Max Normalization (0 ~ 1 정규화)
  for col in numeric_cols:
    if col in gdf.columns:
      min_val = gdf[col].min()
      max_val = gdf[col].max()
      if max_val > min_val:
        gdf[f"{col}_norm"] = (gdf[col] - min_val) / (max_val - min_val)
      else:
        gdf[f"{col}_norm"] = 0.0

  # 좌표계 변환 (WGS84 EPSG:4326 보장)
  if gdf.crs is not None and gdf.crs != "EPSG:4326":
    gdf = gdf.to_crs(epsg=4326)

  return gdf, numeric_cols


gdf, numeric_cols = load_and_prep_geojson("crime_roads.geojson")


# ----------------------------------------------------
# 2. Spectral Gradation 색상 지정 함수
# ----------------------------------------------------
def get_spectral_color(val):
  try:
    val = float(val)
  except (ValueError, TypeError):
    val = 0.0

  if val >= 5.0:
    return "#d7191c"  # 빨강 (High Crime)
  elif val >= 3.0:
    return "#fdae61"  # 주황 (Medium-High Crime)
  elif val > 0.0:
    return "#abdda4"  # 연두/노랑 (Low Crime)
  else:
    return "#2b83ba"  # 파랑 (Zero Crime)


# ----------------------------------------------------
# 3. Streamlit 레이아웃 구성
# ----------------------------------------------------
col1, col2 = st.columns([1, 1])

# --- 왼쪽 컬럼: 지도 시각화 ---
with col1:
  st.subheader("Interactive Crime Roads Map")

  # 지도 중심 설정
  center_lat = gdf.geometry.centroid.y.mean()
  center_lon = gdf.geometry.centroid.x.mean()
  m = folium.Map(location=[center_lat, center_lon], zoom_start=13)

  # GeoJSON 레이어 추가
  folium.GeoJson(
      gdf,
      name="Crime Roads",
      tooltip=folium.GeoJsonTooltip(
          fields=["road_id", "crime_count", "max_speed", "imd_decile"],
          aliases=["Road ID:", "Crime Count:", "Max Speed:", "IMD Decile:"],
      ),
      style_function=lambda feature: {
          "color": get_spectral_color(
              feature["properties"].get("crime_count", 0)
          ),
          "weight": 5,
          "opacity": 0.8,
      },
  ).add_to(m)

  map_output = st_folium(m, width=600, height=500)

# --- 오른쪽 컬럼: 클릭한 도로의 정규화 데이터 바 차트 ---
with col2:
  st.subheader("Normalized Road Characteristics (0 ~ 1)")

  selected_road_id = None
  if map_output and map_output.get("last_active_drawing"):
    props = map_output["last_active_drawing"].get("properties")
    if props:
      selected_road_id = props.get("road_id")

  if selected_road_id is not None:
    # 선택한 도로의 행 데이터 추출
    road_row = gdf[gdf["road_id"] == selected_road_id].iloc[0]

    # 시각화할 차트 데이터프레임 구성
    chart_data = []
    for col in numeric_cols:
      if col in gdf.columns:
        chart_data.append({
            "Variable": col,
            "Normalized Value (0-1)": round(road_row[f"{col}_norm"], 3),
            "Original Value": road_row[col],
        })
    df_chart = pd.DataFrame(chart_data)

    # Plotly 바 차트 생성
    fig = px.bar(
        df_chart,
        x="Variable",
        y="Normalized Value (0-1)",
        text="Normalized Value (0-1)",
        hover_data={"Original Value": True},
        title=f"Normalized Features for Road ID: {selected_road_id}",
        color="Normalized Value (0-1)",
        color_continuous_scale="Viridis",
        range_y=[0, 1.1],
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(showlegend=False)

    st.plotly_chart(fig, use_container_width=True)

    # 원본 변수 상세 정보 표로 표시
    st.write("**Original Feature Values:**")
    st.dataframe(
        df_chart[["Variable", "Original Value", "Normalized Value (0-1)"]],
        hide_index=True,
    )
  else:
    st.info("Click on any road line on the map to display its feature chart.")