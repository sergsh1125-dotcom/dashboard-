import streamlit as st
import pandas as pd
import folium
import json
from streamlit_folium import st_folium
from branca.element import MacroElement
from jinja2 import Template

st.set_page_config(layout="wide")
st.title("Дашборд забезпеченості по регіонах")

# =========================
# ЗАВАНТАЖЕННЯ ФАЙЛУ
# =========================
uploaded_file = st.file_uploader("Завантаж Excel файл", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

    # =========================
    # НОРМАЛІЗАЦІЯ КОЛОНОК
    # =========================
    df.columns = df.columns.str.strip().str.lower()

    column_mapping = {
        "регіон": "region",
        "область": "region",
        "назва регіону": "region",

        "категорія": "category",
        "тип": "category",
        "вид": "category",

        "виріб": "product_name",
        "назва виробу": "product_name",

        "наявна кількість": "available_quantity",
        "кількість в наявності": "available_quantity",

        "потреба": "required_quantity",
        "необхідна кількість": "required_quantity"
    }

    df = df.rename(columns=column_mapping)

    required_columns = [
        "region",
        "product_name",
        "available_quantity",
        "required_quantity"
    ]

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        st.error(f"У файлі відсутні колонки: {missing}")
        st.stop()

    # =========================
    # РОЗРАХУНОК %
    # =========================
    df["available_quantity"] = pd.to_numeric(df["available_quantity"], errors="coerce").fillna(0)
    df["required_quantity"] = pd.to_numeric(df["required_quantity"], errors="coerce").fillna(0)

    grouped = df.groupby("region").agg({
        "available_quantity": "sum",
        "required_quantity": "sum"
    }).reset_index()

    grouped["coverage"] = (grouped["available_quantity"] / grouped["required_quantity"].replace(0, 1)) * 100

    # =========================
    # ЗАВАНТАЖЕННЯ GEOJSON
    # =========================
    with open("ukraine_regions.geojson", "r", encoding="utf-8") as f:
        geojson_data = json.load(f)

    # додаємо coverage у geojson
    for feature in geojson_data["features"]:
        region_name = feature["properties"]["name"].strip().lower()
        match = grouped[grouped["region"].str.strip().str.lower() == region_name]
        if not match.empty:
            feature["properties"]["coverage"] = round(match.iloc[0]["coverage"], 1)
        else:
            feature["properties"]["coverage"] = 0

    # =========================
    # ФУНКЦІЯ КОЛЬОРУ
    # =========================
    def color_by_coverage(value):
        if value < 50:
            return "#d73027"
        elif value < 75:
            return "#f46d43"
        elif value < 100:
            return "#fee08b"
        else:
            return "#1a9850"

    # =========================
    # СТВОРЕННЯ КАРТИ
    # =========================
    m = folium.Map(location=[48.5, 31], zoom_start=6, tiles="cartodbpositron")

    folium.GeoJson(
        geojson_data,
        style_function=lambda f: {
            "fillColor": color_by_coverage(f["properties"].get("coverage", 0)),
            "color": "black",
            "weight": 1,
            "fillOpacity": 0.7
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["name", "coverage"],
            aliases=["Регіон:", "Забезпеченість (%):"],
            localize=True
        )
    ).add_to(m)

    # =========================
    # ЛЕГЕНДА
    # =========================
    legend = MacroElement()
    legend._template = Template("""
    {% macro html(this, kwargs) %}
    <div style="
    position: fixed;
    bottom: 40px;
    left: 40px;
    width: 200px;
    background: white;
    border: 2px solid grey;
    border-radius: 8px;
    padding: 10px;
    font-size: 14px;
    z-index: 9999;
    box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
    ">
    <b>Легенда</b><br><br>

    <div><span style="background:#d73027;width:15px;height:15px;display:inline-block;margin-right:8px;"></span> < 50%</div>
    <div><span style="background:#f46d43;width:15px;height:15px;display:inline-block;margin-right:8px;"></span> 50–74%</div>
    <div><span style="background:#fee08b;width:15px;height:15px;display:inline-block;margin-right:8px;"></span> 75–99%</div>
    <div><span style="background:#1a9850;width:15px;height:15px;display:inline-block;margin-right:8px;"></span> ≥ 100%</div>

    </div>
    {% endmacro %}
    """)

    m.add_child(legend)

    # =========================
    # ВІДОБРАЖЕННЯ
    # =========================
    st.subheader("Карта рівня забезпечення")
    st_folium(m, width=1200, height=650)

else:
    st.info("Завантаж Excel файл для відображення карти.")
