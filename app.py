import ast
import json
import folium
import geopandas as gpd
import pandas as pd
import plotly.express as px
from shapely import wkb
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("Daily Crime Frequency Prediction with Uncertainty in Birmingham")


# ----------------------------------------------------
# 1. 데이터 로드 및 GeoDataFrame 변환 함수
# ----------------------------------------------------
@st.cache_data
def load_crime_roads(geojson_path):
  """crime_roads.geojson 로드 및 정규화"""
  with open(geojson_path, "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

  gdf = gpd.GeoDataFrame.from_features(
      geojson_data["features"], crs="EPSG:4326"
  )

  # 컬럼명 표준화
  rename_dict = {
      "maxspeed": "max_speed",
      "imd_deci": "imd_decile",
      "cri_deci": "cri_decile",
  }
  gdf = gdf.rename(columns={k: v for k, v in rename_dict.items() if k in gdf})

  if "crime_count" not in gdf.columns:
    if "pred_crime" in gdf.columns:
      gdf["crime_count"] = gdf["pred_crime"]
    elif "total_crime" in gdf.columns:
      gdf["crime_count"] = gdf["total_crime"]
    else:
      gdf["crime_count"] = 0.0

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
      min_v = gdf[col].min()
      max_v = gdf[col].max()
      gdf[f"{col}_norm"] = (
          (gdf[col] - min_v) / (max_v - min_v) if max_v > min_v else 0.0
      )

  return gdf, numeric_cols


@st.cache_data
def load_test_roads(csv_path):
  """time_testing_results_clean_withgeom.csv WKB 파싱 및 EPSG:4326 변환"""
  df = pd.read_csv(csv_path)

  # road_id 중복 제거
  df_unique = df.drop_duplicates(subset=["road_id"]).copy()

  # WKB 16진수 문자열 -> Shapely Geometry 변환
  geoms = []
  for g in df_unique["geom"]:
    try:
      geoms.append(wkb.loads(bytes.fromhex(str(g))))
    except Exception:
      geoms.append(None)

  # EPSG:27700 (British National Grid) -> EPSG:4326 (WGS84)
  gdf_test = gpd.GeoDataFrame(
      df_unique, geometry=geoms, crs="EPSG:27700"
  ).to_crs(epsg=4326)
  return gdf_test


# 데이터 읽기
gdf_crime, numeric_cols = load_crime_roads("crime_roads.geojson")
gdf_test = load_test_roads("time_testing_results_clean_withgeom.csv")


# ----------------------------------------------------
# 2. Spectral 색상 지정 함수 (기존 crime_roads용)
# ----------------------------------------------------
def get_spectral_color(val):
  try:
    val = float(val)
  except (ValueError, TypeError):
    val = 0.0

  if val >= 5.0:
    return "#d7191c"
  elif val >= 3.0:
    return "#fdae61"
  elif val > 0.0:
    return "#abdda4"
  else:
    return "#2b83ba"


# ----------------------------------------------------
# 3. Streamlit 레이아웃
# ----------------------------------------------------
col_left, col_right = st.columns([1, 1])

# --- [좌측] 지도 영역 ---
with col_left:
  st.subheader("Probabilistic AI for Smarter and Healthier Cities: A Case Study of Crime Prediction with Uncertainty in Birmingham")

  # 지도 중심점 계산
  bounds = gdf_crime.total_bounds
  center_lat = (bounds[1] + bounds[3]) / 2
  center_lon = (bounds[0] + bounds[2]) / 2

  m = folium.Map(location=[center_lat, center_lon], zoom_start=13)

  # 1) 기존 crime_roads 일반 레이어
  folium.GeoJson(
      gdf_crime,
      name="Crime Roads",
      tooltip=folium.GeoJsonTooltip(
          fields=["road_id", "crime_count", "max_speed", "imd_decile"],
          aliases=["Road ID:", "Crime Count:", "Max Speed:", "IMD Decile:"],
      ),
      style_function=lambda feature: {
          "color": get_spectral_color(
              feature["properties"].get("crime_count", 0)
          ),
          "weight": 4,
          "opacity": 0.7,
      },
  ).add_to(m)

  # 2) time_testing_results 도로 레이어 (Shadow 효과 + Red Dashed 점선)
  # Shadow 레이어 (굵은 검은색 외곽선)
  folium.GeoJson(
      gdf_test,
      name="Test Roads (Shadow)",
      style_function=lambda feature: {
          "color": "#000000",
          "weight": 7,
          "opacity": 0.6,
      },
  ).add_to(m)

  # Main 점선 레이어 (빨간색 점선)
  folium.GeoJson(
      gdf_test,
      name="Test Roads (Dashed)",
      tooltip=folium.GeoJsonTooltip(
          fields=["road_id", "expected_rate_obs", "actual_crime_freq"],
          aliases=["Test Road ID:", "Expected Rate:", "Actual Freq:"],
      ),
      style_function=lambda feature: {
          "color": "#FF3333",
          "weight": 3.5,
          "opacity": 1.0,
          "dashArray": "6, 6",
      },
  ).add_to(m)

  # Map legend
  legend_html = """
  <div style="position: fixed;
              bottom: 30px; left: 30px; width: 190px;
              background-color: white; border: 2px solid grey;
              z-index: 9999; font-size: 12px; padding: 10px;
              box-shadow: 0 0 6px rgba(0,0,0,0.3);">
    <b>Map Legend</b><br>
    <i style="background:#2b83ba; width:16px; height:12px; display:inline-block;"></i>
    &nbsp;Crime count: 0<br>
    <i style="background:#abdda4; width:16px; height:12px; display:inline-block;"></i>
    &nbsp;Crime count: &gt; 0–&lt; 3<br>
    <i style="background:#fdae61; width:16px; height:12px; display:inline-block;"></i>
    &nbsp;Crime count: 3–&lt; 5<br>
    <i style="background:#d7191c; width:16px; height:12px; display:inline-block;"></i>
    &nbsp;Crime count: ≥ 5<br>
    <hr style="margin:6px 0;">
    <span style="border-top:3px dashed #FF3333; width:16px; display:inline-block;"></span>
    &nbsp;Test roads
  </div>
  """
  m.get_root().html.add_child(folium.Element(legend_html))

  map_output = st_folium(m, width=650, height=650)

# --- [우측] 시각화 영역 ---
with col_right:
  # 클릭된 road_id 탐색
  selected_road_id = None
  if map_output and map_output.get("last_active_drawing"):
    props = map_output["last_active_drawing"].get("properties")
    if props:
      selected_road_id = props.get("road_id")

  # 1) [오른쪽 상단] Normalized Bar Chart (단색 적용)
  st.subheader("Normalised Road Characteristics")

  if selected_road_id is not None and selected_road_id in gdf_crime["road_id"].values:
    road_row = gdf_crime[gdf_crime["road_id"] == selected_road_id].iloc[0]
  else:
    road_row = gdf_crime.iloc[0]
    st.info("💡 Click the road segment to check the details.")

  chart_data = []
  for col in numeric_cols:
    if col in gdf_crime.columns:
      chart_data.append(
          {"Variable": col, "Normalized Value (0-1)": road_row[f"{col}_norm"]}
      )
  df_bar = pd.DataFrame(chart_data)

  # 그라데이션 제거 -> 단색(Steel Blue) 바 차트
  fig_bar = px.bar(
      df_bar,
      x="Variable",
      y="Normalized Value (0-1)",
      text_auto=".2f",
      title=f"Road Feature Profile (Road ID: {road_row['road_id']})",
      color_discrete_sequence=["#4682B4"],
      range_y=[0, 1.15],
  )
  fig_bar.update_layout(showlegend=False)
  st.plotly_chart(fig_bar, use_container_width=True)

  # 2) [오른쪽 하단] obs_samples 빨간색 히스토그램
  st.subheader("Sample outputs from BNN for daily crime frequency prediction")

  # 선택된 road_id가 test 세트에 포함되어 있는지 확인
  if (
      selected_road_id is not None
      and selected_road_id in gdf_test["road_id"].values
  ):
    test_row = gdf_test[gdf_test["road_id"] == selected_road_id].iloc[0]
  else:
    test_row = gdf_test.iloc[0]

  # obs_samples 문자열 리스트 파싱
  try:
    obs_samples_list = ast.literal_eval(str(test_row["obs_samples"]))
    df_hist = pd.DataFrame({"obs_samples": obs_samples_list})

    # 빨간색 히스토그램 시각화
    fig_hist = px.histogram(
        df_hist,
        x="Samples of daily crime frequency",
        nbins=30,
        title=f"BNN output for the daily crime frequency prediction (Road ID: {test_row['road_id']})",
        color_discrete_sequence=["#E74C3C"],
    )
    fig_hist.update_layout(
        bargap=0.1, xaxis_title="obs_samples", yaxis_title="Count"
    )
    st.plotly_chart(fig_hist, use_container_width=True)
  except Exception as e:
    st.warning(f"obs_samples 데이터를 불러올 수 없습니다: {e}")

  st.caption(
      "This program acknowledge the financial support of the British Council through the International Science Partnerships Fund (ISPF), Project Application ID 1690, supporting a collaborative research partnership between the United Kingdom and South Korea."
  )

