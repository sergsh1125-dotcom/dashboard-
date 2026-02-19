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

# --- Відповідність назв CSV і GeoJSON ---
region_name_map = {
    "Вінницька область": "Вінницька область",
    "Волинська область": "Волинська область",
    "Дніпропетровська область": "Дніпропетровська область",
    "Донецька область": "Донецька область",
    "Житомирська область": "Житомирська область",
    "Закарпатська область": "Закарпатська область",
    "Запорізька область": "Запорізька область",
    "Івано-Франківська область": "Івано-Франківська область",
    "Київська область": "Київська область",
    "Кіровоградська область": "Кіровоградська область",
    "Луганська область": "Луганська область",
    "Львівська область": "Львівська область",
    "Миколаївська область": "Миколаївська область",
    "Одеська область": "Одеська область",
    "Полтавська область": "Полтавська область",
    "Рівненська область": "Рівненська область",
    "Сумська область": "Сумська область",
    "Тернопільська область": "Тернопільська область",
    "Харківська область": "Харківська область",
    "Херсонська область": "Херсонська область",
    "Хмельницька область": "Хмельницька область",
    "Черкаська область": "Черкаська область",
    "Чернівецька область": "Чернівецька область",
    "Чернігівська область": "Чернігівська область",
    "Київ": "Київ",
    "Автономна Республіка Крим": "Автономна Республіка Крим",
    "Севастополь": "Севастополь"
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
for reg in region_name_map:
    if reg not in region_summary["region_name"].values:
        region_summary = pd.concat(
            [region_summary, pd.DataFrame({"region_name": [reg], "quantity": [0]})],
            ignore_index=True
        )

# --- Додаємо колонку з назвами для GeoJSON ---
region_summary["geojson_name"] = region_summary["region_name"].map(region_name_map)

# --- Завантаження GeoJSON ---
with open("data/ukraine_regions.geojson", "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

# --- Кольорова шкала ---
# 0 -> сірий, середні -> світло-синій, максимум -> синій, гарячі -> червоний
max_quantity = region_summary["quantity"].max()
fig = px.choropleth(
    region_summary,
    geojson=geojson_data,
    locations="geojson_name",
    featureidkey="properties.name",
    color="quantity",
    color_continuous_scale=[
        [0.0, "lightgray"],       # 0
        [0.01, "lightblue"],      # трохи більше 0
        [0.5, "skyblue"],         # середні значення
        [0.8, "blue"],            # високі
        [1.0, "red"]              # гарячі регіони
    ],
    range_color=(0, max_quantity),
    hover_data={"region_name": True, "quantity": True},
)

fig.update_geos(fitbounds="locations", visible=False)
st.plotly_chart(fig, use_container_width=True)

