import streamlit as st
import pandas as pd
import json
import plotly.express as px

st.set_page_config(page_title="Dashboard", layout="wide")

st.title("Інтерактивний дашборд обліку засобів")

# --- Завантаження CSV ---
@st.cache_data
def load_data():
    df = pd.read_csv("data/example_stock.csv")
    
    # Робимо назви колонок "стійкими"
    df.columns = df.columns.str.strip().str.lower()
    
    return df

df = load_data()

# --- Перевірка колонок ---
required_columns = ["region_name", "product_name", "year_of_manufacture", "quantity"]

missing_columns = [col for col in required_columns if col not in df.columns]

if missing_columns:
    st.error(f"У CSV відсутні колонки: {missing_columns}")
    st.write("Знайдені колонки у файлі:")
    st.write(df.columns)
    st.stop()

# --- Фільтр по регіону ---
region = st.selectbox(
    "Оберіть регіон",
    sorted(df["region_name"].unique())
)

filtered_df = df[df["region_name"] == region]

st.subheader("Дані по регіону")
st.dataframe(filtered_df, use_container_width=True)

# --- Агрегація для карти ---
region_summary = (
    df.groupby("region_name")["quantity"]
    .sum()
    .reset_index()
)

# Завантаження GeoJSON
with open("data/ukraine_regions.geojson", "r", encoding="utf-8") as f:
    geojson_data = json.load(f)
st.write("Ключі properties у GeoJSON:")
st.write(geojson_data["features"][0]["properties"])
# --- Карта ---
st.subheader("Карта розподілу кількості засобів")

fig = px.choropleth(
    region_summary,
    geojson=geojson_data,
    locations="region_name",
    featureidkey="properties.name",
    color="quantity",
    color_continuous_scale="Blues",
)

fig.update_geos(fitbounds="locations", visible=False)

st.plotly_chart(fig, use_container_width=True)

