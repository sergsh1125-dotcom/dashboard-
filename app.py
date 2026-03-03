import streamlit as st
import pandas as pd
import json
import folium
from streamlit_folium import st_folium
import io

st.set_page_config(page_title="Dashboard РХБЗ", layout="wide")
st.title("Дашборд забезпечення засобами РХБ захисту")

# =====================================================
# ШАБЛОН EXCEL ДЛЯ ЗАВАНТАЖЕННЯ
# =====================================================

def generate_template():
    template_df = pd.DataFrame({
        "region_name": [],
        "product_name": [],
        "year_of_manufacture": [],
        "quantity": [],
        "required_quantity": []
    })

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        template_df.to_excel(writer, sheet_name="Дані", index=False)

    return output.getvalue()

st.sidebar.download_button(
    label="⬇ Завантажити шаблон Excel",
    data=generate_template(),
    file_name="template_rhbz.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# =====================================================
# 1. ЗАВАНТАЖЕННЯ EXCEL
# =====================================================

st.sidebar.header("Завантаження бази")

uploaded_file = st.sidebar.file_uploader(
    "Завантаж Excel шаблон",
    type=["xlsx"]
)

if uploaded_file is None:
    st.info("⬅ Завантажте Excel файл для початку роботи.")
    st.stop()

df = pd.read_excel(uploaded_file)
df.columns = df.columns.str.strip().str.lower()

required_columns = [
    "region_name",
    "product_name",
    "year_of_manufacture",
    "quantity",
    "required_quantity"
]

if not all(col in df.columns for col in required_columns):
    st.error("У файлі відсутні необхідні колонки.")
    st.write("Знайдені колонки:", df.columns.tolist())
    st.stop()

# очищення числових полів
for col in ["quantity", "required_quantity"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# =====================================================
# 2. ФІЛЬТРИ
# =====================================================

st.sidebar.header("Фільтри")

selected_region = st.sidebar.selectbox(
    "Регіон",
    ["Всі"] + sorted(df["region_name"].unique())
)

selected_product = st.sidebar.selectbox(
    "Засіб РХБЗ",
    ["Всі"] + sorted(df["product_name"].unique())
)

filtered_df = df.copy()

if selected_region != "Всі":
    filtered_df = filtered_df[filtered_df["region_name"] == selected_region]

if selected_product != "Всі":
    filtered_df = filtered_df[filtered_df["product_name"] == selected_product]

# =====================================================
# 3. АГРЕГАЦІЯ
# =====================================================

region_summary = (
    filtered_df
    .groupby("region_name")
    .agg(
        total_quantity=("quantity", "sum"),
        total_required=("required_quantity", "sum")
    )
    .reset_index()
)

def calculate_percent(row):
    if row["total_required"] > 0:
        return round((row["total_quantity"] / row["total_required"]) * 100, 1)
    return 0

region_summary["% забезпечення"] = region_summary.apply(calculate_percent, axis=1)

region_summary["Нестача"] = (
    region_summary["total_required"] - region_summary["total_quantity"]
).apply(lambda x: x if x > 0 else 0)

region_summary["Надлишок"] = (
    region_summary["total_quantity"] - region_summary["total_required"]
).apply(lambda x: x if x > 0 else 0)

# =====================================================
# 4. KPI
# =====================================================

total_quantity = int(region_summary["total_quantity"].sum())
total_required = int(region_summary["total_required"].sum())

col1, col2, col3 = st.columns(3)

col1.metric("Наявність", total_quantity)
col2.metric("Штатна потреба", total_required)

if total_required > 0:
    overall_percent = round((total_quantity / total_required) * 100, 1)
else:
    overall_percent = 0

col3.metric("Загальний % забезпечення", f"{overall_percent}%")

# =====================================================
# 5. ТАБЛИЦЯ
# =====================================================

display_table = region_summary.rename(columns={
    "region_name": "Регіон",
    "total_required": "Штатна потреба",
    "total_quantity": "Наявність"
})[["Регіон","Штатна потреба","Наявність","Нестача","Надлишок","% забезпечення"]]

st.subheader("Інформація по регіонах")
st.dataframe(display_table, use_container_width=True)

# попередження
critical_regions = region_summary[region_summary["% забезпечення"] < 50]
if not critical_regions.empty:
    st.warning("⚠ Є регіони з критичним рівнем забезпечення (<50%)")

# =====================================================
# 6. ГРАФІК
# =====================================================

st.subheader("Рейтинг регіонів за % забезпечення")

chart_df = region_summary.sort_values("% забезпечення", ascending=False)
st.bar_chart(
    chart_df.set_index("region_name")["% забезпечення"]
)

# =====================================================
# 7. КАРТА
# =====================================================

with open("data/ukraine_regions.geojson", "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

region_name_map = {
    "Київ": "Kyiv_city",
    "Київська область": "Kyivska",
    "Львівська область": "Lvivska",
    "Одеська область": "Odeska",
    "Харківська область": "Kharkivska",
    "Дніпропетровська область": "Dnipropetrovska",
    "Полтавська область": "Poltavska",
    "Сумська область": "Sumska",
    "Вінницька область": "Vinnytska",
    "Волинська область": "Volynska",
    "Закарпатська область": "Zakarpatska",
    "Запорізька область": "Zaporizka",
    "Івано-Франківська область": "Ivano-Frankivska",
    "Кіровоградська область": "Kirovohradska",
    "Луганська область": "Luhanska",
    "Миколаївська область": "Mykolaivska",
    "Рівненська область": "Rivnenska",
    "Тернопільська область": "Ternopilska",
    "Херсонська область": "Khersonska",
    "Хмельницька область": "Khmelnytska",
    "Черкаська область": "Cherkaska",
    "Чернігівська область": "Chernihivska",
    "Чернівецька область": "Chernivetska",
    "Житомирська область": "Zhytomyrska"
}

coverage_dict = {}
for ukr_name, eng_name in region_name_map.items():
    value = region_summary.loc[
        region_summary["region_name"] == ukr_name,
        "% забезпечення"
    ]
    coverage_dict[eng_name] = float(value.values[0]) if not value.empty else 0

for feature in geojson_data["features"]:
    eng_name = feature["properties"]["name"]
    feature["properties"]["coverage"] = coverage_dict.get(eng_name, 0)

def color_by_coverage(coverage):
    if coverage == 0:
        return "#ffffff"
    elif coverage < 50:
        return "#d73027"
    elif coverage < 75:
        return "#f46d43"
    elif coverage < 100:
        return "#fee08b"
    else:
        return "#1a9850"

m = folium.Map(
    location=[49, 32],
    zoom_start=6,
    control_scale=True,
    tiles="cartodbpositron"
)

folium.GeoJson(
    geojson_data,
    style_function=lambda feature: {
        "fillColor": color_by_coverage(feature["properties"]["coverage"]),
        "color": "black",
        "weight": 1,
        "fillOpacity": 0.75
    }
).add_to(m)

st.subheader("Карта рівня забезпечення")
st_folium(m, width=1000, height=650)

# =====================================================
# 8. ЕКСПОРТ В EXCEL
# =====================================================

def convert_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Звіт", index=False)
    return output.getvalue()

excel_data = convert_to_excel(display_table)

st.download_button(
    label="📥 Завантажити звіт в Excel",
    data=excel_data,
    file_name="zvit_po_regionakh.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
