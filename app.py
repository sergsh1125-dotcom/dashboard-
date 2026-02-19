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
    st.stop()

# --- Завантаження GeoJSON ---
with open("data/ukraine_regions.geojson", "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

# --- Словник CSV → GeoJSON (транслітеровані назви) ---
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

# --- Додаємо колонку для Plotly ---
region_summary = df.groupby("region_name")["quantity"].sum().reset_index()
region_summary["geojson_name"] = region_summary["region_name"].map(region_name_map)

# --- Додаємо відсутні регіони з нульовою кількістю ---
for name in region_name_map.values():
    if name not in region_summary["geojson_name"].values:
        region_summary = pd.concat(
            [region_summary, pd.DataFrame({"region_name": [name], "quantity": [0], "geojson_name": [name]})],
            ignore_index=True
        )

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

# --- Кольорова шкала ---
max_quantity = region_summary["quantity"].max()
colorscale = [
    [0.0, "lightgray"],
    [0.01, "lightblue"],
    [0.5, "skyblue"],
    [0.8, "blue"],
    [1.0, "red"]
]

# --- Карта ---
st.subheader("Карта розподілу кількості засобів")
fig = px.choropleth(
    region_summary,
    geojson=geojson_data,
    locations="geojson_name",
    featureidkey="properties.name",
    color="quantity",
    color_continuous_scale=colorscale,
    range_color=(0, max_quantity),
    hover_data={"region_name": True, "quantity": True},
)

fig.update_geos(fitbounds="locations", visible=False)
st.plotly_chart(fig, use_container_width=True)

