import streamlit as st
import pandas as pd
import json
import plotly.express as px

st.set_page_config(page_title="Облік засобів", layout="wide")

st.title("Інтерактивний дашборд обліку засобів")

# Завантаження CSV
@st.cache_data
def load_data():
    return pd.read_csv("data/example_stock.csv")

df = load_data()

# Перевірка наявності необхідних колонок
required_columns = ["Регіон", "Підрозділ", "Засіб", "Кількість"]
for col in required_columns:
    if col not in df.columns:
        st.error(f"У CSV відсутня колонка: {col}")
        st.stop()

# Фільтр по регіону
region = st.selectbox("Оберіть регіон", sorted(df["Регіон"].unique()))

filtered_df = df[df["Регіон"] == region]

st.subheader("Таблиця даних")
st.dataframe(filtered_df, use_container_width=True)

# Агрегація по регіонах
region_summary = df.groupby("Регіон")["Кількість"].sum().reset_index()

# Завантаження GeoJSON
with open("data/ukraine_regions.geojson", "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

st.subheader("Карта кількості засобів по регіонах")

fig = px.choropleth(
    region_summary,
    geojson=geojson_data,
    locations="Регіон",
    featureidkey="properties.name",
    color="Кількість",
    color_continuous_scale="Blues",
)

fig.update_geos(fitbounds="locations", visible=False)
st.plotly_chart(fig, use_container_width=True)

