import streamlit as st
import pandas as pd
import json
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Dashboard", layout="wide")
st.title("Інтерактивний дашборд обліку засобів (Folium)")

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
    st.stop()

# --- Фільтри ---
st.sidebar.header("Фільтри")
selected_region = st.sidebar.selectbox("Оберіть регіон", ["Всі"] + sorted(df["region_name"].unique()))
selected_year = st.sidebar.selectbox("Оберіть рік виготовлення", ["Всі"] + sorted(df["year_of_manufacture"].astype(str).unique()))
selected_product = st.sidebar.selectbox("Оберіть продукт", ["Всі"] + sorted(df["product_name"].unique()))

filtered_df = df.copy()
if selected_region != "Всі":
    filtered_df = filtered_df[filtered_df["region_name"] == selected_region]
if selected_year != "Всі":
    filtered_df = filtered_df[filtered_df["year_of_manufacture"].astype(str) == selected_year]
if selected_product != "Всі":
    filtered_df = filtered_df[filtered_df["product_name"] == selected_product]

st.subheader("Дані по фільтру")
st.dataframe(filtered_df, use_container_width=True)

# --- Агрегація даних ---
region_summary = filtered_df.groupby("region_name")["quantity"].sum().reset_index()

# --- Завантаження GeoJSON ---
with open("data/ukraine_regions.geojson", "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

# --- Словник CSV → GeoJSON ---
region_name_map = {
    "Автономна Республіка Крим": "Avtonomna Respublika Krym",
    "Черкаська область": "Cherkaska",
    "Чернігівська область": "Chernihivska",
    "Чернівецька область": "Chernivetska",
    "Дніпропетровська область": "Dnipropetrovska",
    "Донецька область": "Donetska",
    "Івано-Франківська область": "Ivano-Frankivska",
    "Харківська область": "Kharkivska",
    "Херсонська область": "Khersonska",
    "Хмельницька область": "Khmelnytska",
    "Кіровоградська область": "Kirovohradska",
    "Київська область": "Kyivska",
    "Луганська область": "Luhanska",
    "Львівська область": "Lvivska",
    "Миколаївська область": "Mykolaivska",
    "Одеська область": "Odeska",
    "Полтавська область": "Poltavska",
    "Рівненська область": "Rivnenska",
    "Севастополь": "Sevastopilska",
    "Сумська область": "Sumska",
    "Тернопільська область": "Ternopilska",
    "Вінницька область": "Vinnytska",
    "Волинська область": "Volynska",
    "Закарпатська область": "Zakarpatska",
    "Запорізька область": "Zaporizka",
    "Житомирська область": "Zhytomyrska",
    "Київ": "Kyiv"
}

# --- Додаємо кількість у GeoJSON ---
for feature in geojson_data["features"]:
    geo_name = feature["properties"]["name"]
    # знаходимо українську назву з CSV
    csv_name = [k for k, v in region_name_map.items() if v == geo_name]
    if csv_name:
        qty = int(region_summary.loc[region_summary["region_name"] == csv_name[0], "quantity"].sum())
    else:
        qty = 0
    feature["properties"]["quantity"] = qty

# --- Створюємо карту ---
m = folium.Map(location=[49, 32], zoom_start=6)

def color_by_quantity(qty):
    if qty == 0:
        return "lightgray"
    elif qty <= 10:
        return "lightblue"
    elif qty <= 50:
        return "blue"
    else:
        return "red"

folium.GeoJson(
    geojson_data,
    style_function=lambda feature: {
        "fillColor": color_by_quantity(feature["properties"]["quantity"]),
        "color": "black",
        "weight": 1,
        "fillOpacity": 0.6
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["name", "quantity"],
        aliases=["Регіон", "Кількість"],
        localize=True
    )
).add_to(m)

st.subheader("Карта розподілу кількості засобів")
st_folium(m, width=900, height=600)

