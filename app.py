import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.wkt import loads
import folium
from streamlit_folium import st_folium
import plotly.express as px

st.set_page_config(layout="wide")

@st.cache_data
def load_geom_data():
    df = pd.read_csv("time_testing_results_clean_withgeom.csv")
    
    # geometry 컬럼이 WKT 문자열 형식인 경우 처리
    if "geometry" in df.columns:
        if isinstance(df["geometry"].iloc[0], str):
            df["geometry"] = df["geometry"].apply(loads)
        gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
    else:
        gdf = df
    return gdf

# 데이터 로드
try:
    gdf = load_geom_data()
except Exception as e:
    st.error(f"데이터를 로드하는 중 오류가 발생했습니다: {e}")
    st.stop()

# 레이아웃 구성 (좌측: 지도, 우측: 차트)
col_left, col_right = st.columns([6, 4])

# -----------------------------------------------------------------------------
# 좌측: 지도 (Road Geometries 표시)
# -----------------------------------------------------------------------------
with col_left:
    st.subheader("Road Geometries Map")
    
    # 지도 중심 설정
    bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="CartoDB positron")
    
    # 1. 그림자(Shadow) 효과 라인
    folium.GeoJson(
        gdf,
        style_function=lambda feature: {
            'color': '#2C3E50',
            'weight': 6,
            'opacity': 0.4,
        },
        name="Road Shadow"
    ).add_to(m)
    
    # 2. 메인 점선(Dashed) 스타일 라인
    folium.GeoJson(
        gdf,
        style_function=lambda feature: {
            'color': '#E74C3C',
            'weight': 3,
            'opacity': 0.9,
            'dashArray': '6, 6'
        },
        tooltip=folium.GeoJsonTooltip(fields=[col for col in ['id', 'obs_samples'] if col in gdf.columns]),
        name="Test Roads"
    ).add_to(m)

    st_folium(m, width=None, height=700, use_container_width=True)

# -----------------------------------------------------------------------------
# 우측: 시각화 차트 영역
# -----------------------------------------------------------------------------
with col_right:
    # 1. 오른쪽 상단: Normalized Bar Chart (단색 적용)
    st.subheader("Normalized Value Bar Chart")
    
    # 예시 데이터프레임 컬럼 구조에 맞춰 수정 가능 (예: 'category', 'normalized_value')
    if "normalized_value" in gdf.columns:
        fig_bar = px.bar(
            gdf, 
            x=gdf.index, 
            y="normalized_value",
            color_discrete_sequence=["#4682B4"]  # 단색 (SteelBlue) 설정
        )
        fig_bar.update_layout(
            margin=dict(l=20, r=20, t=30, b=20),
            xaxis_title="Index",
            yaxis_title="Normalized Value"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # 2. 오른쪽 하단: obs_samples 빨간색 히스토그램
    st.subheader("Observation Samples Histogram")
    
    if "obs_samples" in gdf.columns:
        fig_hist = px.histogram(
            gdf, 
            x="obs_samples",
            color_discrete_sequence=["#E74C3C"],  # 빨간색 단색 설정
            nbins=30
        )
        fig_hist.update_layout(
            margin=dict(l=20, r=20, t=30, b=20),
            xaxis_title="Observation Samples",
            yaxis_title="Count",
            bargap=0.1
        )
        st.plotly_chart(fig_hist, use_container_width=True)