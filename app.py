import streamlit as st
import pandas as pd
import io
import json
import folium
from streamlit_folium import st_folium
from openpyxl.styles import PatternFill, Protection
from openpyxl.worksheet.datavalidation import DataValidation

st.set_page_config(page_title="Dashboard РХБЗ", layout="wide")
st.title("Стан забезпечення підрозділів ОРСЦЗ засобами РХБ захисту")

# =====================================================
# 2. ЗАВАНТАЖЕННЯ EXCEL
# =====================================================

uploaded_file = st.sidebar.file_uploader("Завантаж Excel файл", type=["xlsx"])

if uploaded_file is None:
    st.info("⬅ Завантажте Excel файл")
    st.stop()

df = pd.read_excel(uploaded_file)

df.columns = df.columns.str.strip().str.lower()

for col in ["quantity","required_quantity"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# =====================================================
# 3. ФІЛЬТРИ
# =====================================================

st.sidebar.header("Фільтри")

selected_region = st.sidebar.selectbox(
    "Регіон",
    ["Всі"] + sorted(df["region_name"].unique())
)

selected_product = st.sidebar.selectbox(
    "Засіб",
    ["Всі"] + sorted(df["product_name"].unique())
)

filtered_df = df.copy()

if selected_region != "Всі":
    filtered_df = filtered_df[filtered_df["region_name"] == selected_region]

if selected_product != "Всі":
    filtered_df = filtered_df[filtered_df["product_name"] == selected_product]

# =====================================================
# 4. АГРЕГАЦІЯ
# =====================================================

region_summary = (
    filtered_df
    .groupby("region_name")
    .agg(
        total_quantity=("quantity","sum"),
        total_required=("required_quantity","sum")
    )
    .reset_index()
)

region_summary["% забезпечення"] = region_summary.apply(
    lambda row: round((row["total_quantity"]/row["total_required"])*100,1)
    if row["total_required"]>0 else 0,
    axis=1
)

region_summary["Нестача"] = (
    region_summary["total_required"] - region_summary["total_quantity"]
).clip(lower=0)

region_summary["Надлишок"] = (
    region_summary["total_quantity"] - region_summary["total_required"]
).clip(lower=0)

# =====================================================
# 5. KPI
# =====================================================

total_quantity = int(region_summary["total_quantity"].sum())
total_required = int(region_summary["total_required"].sum())

col1,col2,col3 = st.columns(3)

col1.metric("Наявність", total_quantity)
col2.metric("Потреба", total_required)

percent_total = round((total_quantity/total_required)*100,1) if total_required>0 else 0
col3.metric("% забезпечення", f"{percent_total}%")

# =====================================================
# 6. ТАБЛИЦЯ
# =====================================================

display_table = region_summary.rename(columns={
"region_name":"Регіон",
"total_quantity":"Наявність",
"total_required":"Потреба"
})

st.subheader("Дані по регіонах")

st.dataframe(display_table, use_container_width=True)

# =====================================================
# 7. ГРАФІК
# =====================================================

st.subheader("Рейтинг регіонів")

st.bar_chart(
    region_summary
    .sort_values("% забезпечення", ascending=False)
    .set_index("region_name")["% забезпечення"]
)

# =====================================================
# 8. КАРТА (ПОВНИЙ ТА ВИПРАВЛЕНИЙ БЛОК)
# =====================================================
import os

st.subheader("Карта стану забезпечення засобами РХБ захисту")

# 1. Словник відповідності назв (Обов'язково має бути тут або вище по коду)
region_name_map = {
    "Київ": "Kyiv_city",
    "Вінницька область": "Vinnytska",
    "Волинська область": "Volynska",
    "Дніпропетровська область": "Dnipropetrovska",
    "Донецька область": "Donetska",
    "Житомирська область": "Zhytomyrska",
    "Закарпатська область": "Zakarpatska",
    "Запорізька область": "Zaporizka",
    "Івано-Франківська область": "Ivano-Frankivska",
    "Київська область": "Kyivska",
    "Кіровоградська область": "Kirovohradska",
    "Луганська область": "Luhanska",
    "Львівська область": "Lvivska",
    "Миколаївська область": "Mykolaivska",
    "Одеська область": "Odeska",
    "Полтавська область": "Poltavska",
    "Рівненська область": "Rivnenska",
    "Сумська область": "Sumska",
    "Тернопільська область": "Ternopilska",
    "Харківська область": "Kharkivska",
    "Херсонська область": "Khersonska",
    "Хмельницька область": "Khmelnytska",
    "Черкаська область": "Cherkaska",
    "Чернівецька область": "Chernivetska",
    "Чернігівська область": "Chernihivska"
}

# Перевірка наявності файлу GeoJSON
geojson_path = "data/ukraine_regions.geojson"

if not os.path.exists(geojson_path):
    st.error(f"❌ Файл геоданих не знайдено за шляхом: {geojson_path}. Перевірте папку 'data'.")
else:
    with open(geojson_path, "r", encoding="utf-8") as f:
        geojson_data = json.load(f)

    # 2. Підготовка даних для відображення
    map_data_lookup = {}
    for ukr_name, eng_name in region_name_map.items():
        row = region_summary[region_summary["region_name"] == ukr_name]
        if not row.empty:
            map_data_lookup[eng_name] = {
                "coverage": row["% забезпечення"].values[0],
                "shortage": int(row["Нестача"].values[0]),
                "total_q": int(row["total_quantity"].values[0]),
                "ukr_name": ukr_name
            }
        else:
            map_data_lookup[eng_name] = {
                "coverage": 0, "shortage": 0, "total_q": 0, "ukr_name": ukr_name
            }

    # 3. Збагачуємо GeoJSON даними для Tooltip
    for feature in geojson_data["features"]:
        eng_name = feature["properties"]["name"]
        data = map_data_lookup.get(eng_name, {})
        feature["properties"]["ukr_label"] = data.get("ukr_name", eng_name)
        feature["properties"]["coverage_val"] = f"{data.get('coverage', 0)}%"
        feature["properties"]["shortage_val"] = f"{data.get('shortage', 0)} шт."
        feature["properties"]["total_val"] = f"{data.get('total_q', 0)} шт."

    # 4. Функція кольору
    def color_by_coverage(c):
        if c >= 100: return "#1a9850"   # Темно-зелений
        if c >= 86:  return "#91cf60"   # Світло-зелений
        if c >= 71:  return "#fee08b"   # Жовтий
        if c >= 51:  return "#fc8d59"   # Помаранчевий
        return "#d73027"                # Червоний

    # 5. Стиль регіону
    def style_function(feature):
        eng_name = feature["properties"]["name"]
        coverage = map_data_lookup.get(eng_name, {}).get("coverage", 0)
        
        if selected_region != "Всі":
            eng_selected = region_name_map.get(selected_region)
            if eng_name != eng_selected:
                return {
                    "fillColor": "#d9d9d9", "color": "#666666", "weight": 1, "fillOpacity": 0.2
                }
        
        return {
            "fillColor": color_by_coverage(coverage),
            "color": "black", "weight": 1.2, "fillOpacity": 0.75
        }

    # 6. Створення карти
    m = folium.Map(location=[48.3, 31.1], zoom_start=6, tiles="cartodbpositron")

    tooltip = folium.GeoJsonTooltip(
        fields=["ukr_label", "coverage_val", "total_val", "shortage_val"],
        aliases=["Регіон:", "Забезпечення:", "Наявність:", "Нестача:"],
        localize=True, sticky=False, labels=True,
        style="background-color: #F0EFEF; border: 1px solid black; border-radius: 3px;"
    )

    folium.GeoJson(geojson_data, style_function=style_function, tooltip=tooltip).add_to(m)

    # 7. Легенда з фіксованим кольором тексту
    legend_html = """
    <div style="
    position: fixed; 
    bottom: 50px; left: 50px; width: 230px; height: 165px; 
    background-color: white; 
    color: black; /* Явно вказуємо чорний колір тексту */
    border: 2px solid grey; 
    z-index: 9999; 
    font-size: 14px;
    padding: 10px; 
    border-radius: 5px; 
    box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
    ">
    <b style="color: black;">Рівень забезпечення (%)</b><br>
    <div style="margin-top: 8px; line-height: 1.6;">
        <i style="background: #1a9850; width: 14px; height: 14px; float: left; margin-right: 10px; border-radius: 50%; border: 1px solid #333;"></i> 100% та більше<br>
        <i style="background: #91cf60; width: 14px; height: 14px; float: left; margin-right: 10px; border-radius: 50%; border: 1px solid #333;"></i> 86% – 99%<br>
        <i style="background: #fee08b; width: 14px; height: 14px; float: left; margin-right: 10px; border-radius: 50%; border: 1px solid #333;"></i> 71% – 85%<br>
        <i style="background: #fc8d59; width: 14px; height: 14px; float: left; margin-right: 10px; border-radius: 50%; border: 1px solid #333;"></i> 51% – 70%<br>
        <i style="background: #d73027; width: 14px; height: 14px; float: left; margin-right: 10px; border-radius: 50%; border: 1px solid #333;"></i> 0% – 50%
    </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    st_folium(m, width="100%", height=600)
# =====================================================
# 9. ЕКСПОРТ
# =====================================================

def convert_to_excel(df):

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    return output.getvalue()

st.download_button(
    "📥 Завантажити звіт Excel",
    convert_to_excel(display_table),
    "zvit.xlsx"
)
