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

# --- Словник регіонів для GeoJSON ---
regions_geojson_uk = {
    "Вінницька область": None,
    "Волинська область": None,
    "Дніпропетровська область": None,
    "Донецька область": None,
    "Житомирська область": None,
    "Закарпатська область": None,
    "Запорізька область": None,
    "Івано-Франківська область": None,
    "Київська область": None,
    "Кіровоградська область": None,
    "Луганська область": None,
    "Львівська область": None,
    "Миколаївська область": None,
    "Одеська область": None,
    "Полтавська область": None,
    "Рівненська область": None,
    "Сумська область": None,
    "Тернопільська область": None,
    "Харківська область": None,
    "Херсонська область": None,
    "Хмельницька область": None,
    "Черкаська область": None,
    "Чернівецька область": None,
    "Чернігівська область": None,
    "Київ": None,
    "Автономна Республіка Крим": None,
    "Севастополь": None
}

# --- Фільтри ---
st.sidebar.header("Фільтри")
selected_region = st.sidebar.selectbox("Оберіть регіон", ["Всі"] + sorted(df["region_name"].unique()))
selected_year = st.sidebar.selectbox("Оберіть рік виготовлення", ["Всі"] + sorted(df["year_of_manufacture"].astype(str).unique()))
selected_product = st.sidebar.selectbox("Оберіть продукт", ["Всі"] + sorted(df["product_name"].unique()))

# --- Фільтрація даних ---
filtered_df = df.copy()
if selected_region != "Всі":
    filtered_df = filtered_df[filtered_df["region_name"] == selected_region]
if selected_year != "Всі":
    filtered_df = filtered_df[filtered_df["year_of_manufacture"].astype(str) == selected_year]
if selected_product != "Всі":
    filtered_df = filtered_df[filtered_df["product_name"] == selected_product]

# --- Показ таблиці ---
st.subheader("Дані по фільтру")
st.dataframe(filtered_df, use_container_width=True)

# --- Агрегація даних для карти ---
region_summary = (
    filtered_df.groupby("region_name")["quantity"]
    .sum()
    .reset_index()
)

# --- Додаємо відсутні регіони з нульовою кількістю ---
for reg in regions_geojson_uk:
    if reg not in region_summary["region_name"].values:
        region_summary = pd.concat(
            [region_summary, pd.DataFrame({"region_name": [reg], "quantity": [0]})],
            ignore_index=True
        )

# --- Завантаження GeoJSON ---
with open("data/ukraine_regions.geojson", "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

# --- Динамічна кольорова шкала ---
max_quantity = region_summary["quantity"].max()

# --- Карта з підписами ---
st.subheader("Карта розподілу кількості засобів")

fig = px.choropleth(
    region_summary,
    geojson=geojson_data,
    locations="region_name",
    featureidkey="properties.name",
    color="quantity",
    color_continuous_scale="Blues",
    range_color=(0, max_quantity),
    hover_data={"region_name": True, "quantity": True},  # підписи при наведенні
)

fig.update_geos(fitbounds="locations", visible=False)
st.plotly_chart(fig, use_container_width=True)

